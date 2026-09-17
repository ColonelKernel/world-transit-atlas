#!/usr/bin/env Rscript
# =============================================================================
# World Transit Network Atlas — R access layer
# -----------------------------------------------------------------------------
# Loads every dataset the Atlas has produced, joins them into analysis-ready
# frames, and shows how to (a) work with the bundled files and (b) pull the
# live open-data feeds directly from R. Mirrors the Python loader fetch_ridership.py.
#
#   Datasets (all under DATA_DIR, your "Transit Network Maps" Drive folder):
#     ridership/ridership_long.csv    tidy panel: one row per (system, period)
#     research/system_attributes.csv  opening year, automation, ownership, farebox
#     research/covariates.csv         population, density, GDP/cap, motorization, trips/cap
#     research/coords.json            lat/lon for all 201 systems
#     networks/new-york.json          real NYC subway stations + line geometry
#     networks/chicago.json           real Chicago 'L' stations + line geometry
#
#   Usage:  Rscript transit_atlas.R        # runs the demo analyses at the bottom
#           # or  source("transit_atlas.R") in an interactive session and use the frames
# =============================================================================

## ---- 0. packages -----------------------------------------------------------
# install.packages(c("tidyverse","jsonlite"))   # sf + scales optional (geometry/plots)
suppressPackageStartupMessages({
  library(tidyverse)   # dplyr, tidyr, readr, ggplot2, purrr
  library(jsonlite)    # read the JSON files + hit the open-data APIs
})

## ---- 1. where the data lives -----------------------------------------------
# Point this at your Google Drive "Transit Network Maps" folder. The default
# tries an env var, then the Drive path, then the current directory.
DATA_DIR <- Sys.getenv("TRANSIT_DATA_DIR", unset = NA)
if (is.na(DATA_DIR)) {
  candidates <- c(
    "~/Library/CloudStorage/GoogleDrive-zachscheffler@gmail.com/My Drive/Transit Network Maps",
    "."
  )
  DATA_DIR <- candidates[which(dir.exists(path.expand(candidates)))[1]]
}
DATA_DIR <- path.expand(DATA_DIR)
p <- function(...) file.path(DATA_DIR, ...)
message("Reading Atlas data from: ", DATA_DIR)

## ---- 2. load the tidy files ------------------------------------------------

# 2a. Cross-sectional table: one row per system, everything joined.
#     covariates.csv already carries the latest annual ridership + attributes +
#     city covariates + country covariates, so it is the natural "systems" table.
systems <- readr::read_csv(p("research", "covariates.csv"), show_col_types = FALSE) |>
  mutate(
    ownership_level      = na_if(ownership_level, ""),
    log_density          = log10(density_per_km2),
    log_trips_per_capita = log10(trips_per_capita)
  )

# 2b. Coordinates (lat/lon) — join on for mapping.
coords <- jsonlite::fromJSON(p("research", "coords.json")) |>
  as_tibble() |>
  select(slug, lat, lon)
systems <- left_join(systems, coords, by = "slug")

# 2c. The monthly / annual PANEL (for time series — the COVID dip, recovery, etc.)
ridership <- readr::read_csv(p("ridership", "ridership_long.csv"), show_col_types = FALSE) |>
  mutate(period_start = as.Date(period_start))
# Just the 33 real monthly series:
monthly <- ridership |> filter(granularity == "monthly")

## ---- 3. load a metro network (real line + station geometry) -----------------
# Returns a list with $stations (tibble: name, lon, lat, routes) and
# $lines (tibble: route, color, paths) where paths is a list-column of
# coordinate matrices. Works for the cities in networks/ (new-york, chicago).
load_network <- function(slug) {
  net <- jsonlite::fromJSON(p("networks", paste0(slug, ".json")),
                            simplifyVector = FALSE)
  stations <- map_dfr(net$stations, ~ tibble(
    name = .x$name, lon = .x$lon, lat = .x$lat,
    routes = .x$routes %||% NA_character_
  ))
  lines <- map_dfr(net$lines, function(ln) tibble(
    route = ln$route, color = ln$color,
    paths = list(lapply(ln$paths, function(pth)
      do.call(rbind, lapply(pth, function(pt) c(pt[[1]], pt[[2]])))))
  ))
  list(stations = stations, lines = lines)
}

## ---- 4. pull the data LIVE from the open-data APIs (reproducible) -----------
# The bundled CSVs were built from these feeds; here's how to refresh them in R.

# 4a. US National Transit Database — monthly rail UPT for any agency since 2002.
#     ntd_id per system is in ridership/ntd_map.json.
ntd_rail_modes <- c("HR", "LR", "MG", "YR", "CC")  # heavy/light/monorail/hybrid/cable
fetch_ntd_rail_monthly <- function(ntd_id) {
  modes <- paste0("'", ntd_rail_modes, "'", collapse = ",")
  q <- sprintf(paste0(
    "$select=date_trunc_ym(date) AS ym, sum(upt) AS riders",
    "&$where=ntd_id='%s' AND mode in(%s)&$group=ym&$order=ym&$limit=100000"),
    ntd_id, modes)
  url <- paste0("https://data.transportation.gov/resource/8bui-9xvu.json?",
                URLencode(q, reserved = TRUE))
  jsonlite::fromJSON(url) |>
    as_tibble() |>
    transmute(ym = substr(ym, 1, 7), riders = as.numeric(riders))
}
# example:  fetch_ntd_rail_monthly("20008")   # New York City Transit

# 4b. Any Socrata daily feed -> monthly (e.g. Chicago 'L' entries 5neh-572f).
fetch_socrata_monthly <- function(domain, dataset, datef, valf) {
  q <- sprintf(paste0("$select=date_trunc_ym(%s) AS ym, sum(%s) AS riders",
                      "&$group=ym&$order=ym&$limit=100000"), datef, valf)
  url <- sprintf("https://%s/resource/%s.json?%s", domain, dataset,
                 URLencode(q, reserved = TRUE))
  jsonlite::fromJSON(url) |> as_tibble() |>
    transmute(ym = substr(ym, 1, 7), riders = as.numeric(riders))
}

# 4c. World Bank indicator for a country (GDP/capita, motorization, ...).
fetch_worldbank <- function(iso3, indicator = "NY.GDP.PCAP.CD") {
  url <- sprintf("https://api.worldbank.org/v2/country/%s/indicator/%s?format=json&per_page=100",
                 iso3, indicator)
  raw <- jsonlite::fromJSON(url)
  as_tibble(raw[[2]]) |> transmute(year = as.integer(date), value) |> arrange(year)
}

## ---- 5. demo analyses ------------------------------------------------------
run_demos <- function() {
  dir.create("atlas_out", showWarnings = FALSE)

  # (i) The headline relationship: density -> transit use, cars -> against it.
  #     Hong Kong (267 trips/cap, 24,500/km2, 124 cars) vs LA (4.4, 2,250, 779).
  fig1 <- systems |>
    filter(!is.na(trips_per_capita), !is.na(density_per_km2)) |>
    ggplot(aes(density_per_km2, trips_per_capita,
               size = annual_riders, colour = region)) +
    geom_point(alpha = .7) +
    geom_text(aes(label = ifelse(trips_per_capita > 150 | trips_per_capita < 6 |
                                 annual_riders > 2.5e9, city, "")),
              size = 3, vjust = -1, show.legend = FALSE) +
    scale_x_log10() + scale_y_log10() +
    labs(title = "Density drives metro use; car ownership fights it",
         x = "Urban density (people / km2, log)",
         y = "Metro trips per capita per year (log)",
         size = "Annual riders", colour = "Region") +
    theme_minimal()
  ggsave("atlas_out/trips_vs_density.png", fig1, width = 9, height = 6, dpi = 130)

  # (ii) The COVID cliff and recovery, indexed to Feb 2020 = 100.
  fig2 <- monthly |>
    filter(system_id %in% c("new-york","london","sao-paulo","hong-kong","santiago")) |>
    group_by(system_id) |>
    mutate(base = value[period_start == as.Date("2020-02-01")][1],
           idx  = 100 * value / base) |>
    ungroup() |>
    ggplot(aes(period_start, idx, colour = system_id)) +
    geom_hline(yintercept = 100, linewidth = .3, colour = "grey70") +
    annotate("rect", xmin = as.Date("2020-03-01"), xmax = as.Date("2020-06-01"),
             ymin = -Inf, ymax = Inf, alpha = .08, fill = "red") +
    geom_line(linewidth = .7) +
    labs(title = "Ridership vs. Feb-2020 baseline", x = NULL,
         y = "Index (Feb 2020 = 100)", colour = NULL) +
    theme_minimal()
  ggsave("atlas_out/covid_index.png", fig2, width = 9, height = 5, dpi = 130)

  # (iii) Farebox recovery by ownership model.
  fb <- systems |>
    filter(!is.na(farebox_recovery_pct)) |>
    mutate(farebox_recovery_pct = as.numeric(farebox_recovery_pct))
  print(fb |> group_by(region) |>
          summarise(n = n(), median_farebox = median(farebox_recovery_pct)) |>
          arrange(desc(median_farebox)))

  # (iv) Draw a real network from geometry (NYC), coloured by line.
  tryCatch({
    nyc <- load_network("new-york")
    lseg <- nyc$lines |>
      mutate(seg = map(paths, ~ imap_dfr(.x, function(m, i)
        as_tibble(m) |> setNames(c("lon","lat")) |> mutate(part = i)))) |>
      select(route, color, seg) |> unnest(seg)
    fig4 <- ggplot() +
      geom_path(data = lseg, aes(lon, lat, group = interaction(route, part),
                                 colour = color), linewidth = .5) +
      geom_point(data = nyc$stations, aes(lon, lat), size = .5,
                 colour = "white", alpha = .6) +
      scale_colour_identity() + coord_quickmap() +
      labs(title = sprintf("New York City Subway — %d stations, %d lines",
                           nrow(nyc$stations), nrow(nyc$lines))) +
      theme_void() + theme(plot.background = element_rect(fill = "#0b0e16", colour = NA),
                           plot.title = element_text(colour = "grey85"))
    ggsave("atlas_out/nyc_network.png", fig4, width = 7, height = 8, dpi = 130)
  }, error = function(e) message("network demo skipped: ", conditionMessage(e)))

  message("Wrote plots to ./atlas_out/  |  systems = ", nrow(systems),
          " ; monthly rows = ", nrow(monthly))
}

## ---- 6. quick peek + run ---------------------------------------------------
`%||%` <- function(a, b) if (is.null(a)) b else a
cat("\nSystems table:", nrow(systems), "rows x", ncol(systems), "cols\n")
cat("Top 5 by trips per capita:\n")
systems |> arrange(desc(trips_per_capita)) |>
  select(city, country, trips_per_capita, density_per_km2, motorization_per_1000) |>
  head(5) |> print()

if (sys.nframe() == 0) run_demos()   # runs when called via Rscript, not on source()
