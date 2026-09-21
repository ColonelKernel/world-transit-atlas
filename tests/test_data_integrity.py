#!/usr/bin/env python3
"""
Data-integrity gates for the atlas.

The repo's claims are all checkable against the repo's own files, and until now
none of them were checked. Two concrete failures are what this suite exists to
prevent:

  - "1,303 lines" stood in the README until the count was re-run and turned out
    to be 1,298. A number written from memory drifts silently; a number asserted
    against the data cannot.
  - `index.html` is generated from `data/`, so editing the data without
    rebuilding leaves a page that disagrees with the dataset it claims to show.

Stdlib only, except that test_build_is_reproducible imports the generator.
Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORKS = os.path.join(ROOT, "data", "networks")
README = os.path.join(ROOT, "README.md")
sys.path.insert(0, os.path.join(ROOT, "tools"))


def load_networks() -> dict[str, dict]:
    out = {}
    for path in sorted(glob.glob(os.path.join(NETWORKS, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            out[os.path.basename(path)[:-5]] = json.load(fh)
    return out


def readme() -> str:
    with open(README, encoding="utf-8") as fh:
        return fh.read()


class TestNetworkFiles(unittest.TestCase):
    """Every per-city file parses and carries usable geometry."""

    @classmethod
    def setUpClass(cls):
        cls.nets = load_networks()

    def test_every_file_has_the_schema(self):
        for slug, d in self.nets.items():
            with self.subTest(slug=slug):
                self.assertEqual({"slug", "city", "stations", "lines"}, set(d),
                                 f"{slug}: unexpected or missing top-level keys")
                self.assertEqual(d["slug"], slug, f"{slug}: slug disagrees with filename")
                self.assertTrue(d["city"], f"{slug}: empty city name")

    def test_no_city_is_empty(self):
        """The whole point of the coverage work: no station-only, no line-only."""
        for slug, d in self.nets.items():
            with self.subTest(slug=slug):
                self.assertTrue(d["stations"], f"{slug}: no stations")
                self.assertTrue(d["lines"], f"{slug}: no line geometry")

    def test_coordinates_are_on_earth(self):
        for slug, d in self.nets.items():
            with self.subTest(slug=slug):
                for s in d["stations"]:
                    self.assertTrue(-180 <= s["lon"] <= 180 and -90 <= s["lat"] <= 90,
                                    f"{slug}: station {s.get('name')!r} off-globe")
                for ln in d["lines"]:
                    for path in ln["paths"]:
                        self.assertGreaterEqual(len(path), 2,
                                                f"{slug}: line {ln['route']} has a 1-point path")
                        for lon, lat in path:
                            self.assertTrue(-180 <= lon <= 180 and -90 <= lat <= 90,
                                            f"{slug}: line {ln['route']} leaves the globe")

    def test_lines_carry_a_colour(self):
        for slug, d in self.nets.items():
            for ln in d["lines"]:
                with self.subTest(slug=slug, route=ln["route"]):
                    self.assertRegex(str(ln["color"]), r"^#[0-9a-fA-F]{3,8}$",
                                     f"{slug}: line {ln['route']} colour is not a hex triplet")

    def test_no_depot_or_disused_alignments(self):
        """Passenger routes only -- depot tracks and heritage spurs were stripped."""
        bad = re.compile(r"former|disused|abandoned|proposed|siding|depot|not in use", re.I)
        for slug, d in self.nets.items():
            for ln in d["lines"]:
                with self.subTest(slug=slug, route=ln["route"]):
                    self.assertIsNone(bad.search(str(ln["route"])),
                                      f"{slug}: {ln['route']!r} is not a passenger line")


class TestGeometryIsWhereItClaims(unittest.TestCase):
    """Line geometry has to sit near the city it is filed under.

    The fetcher sweeps a fixed radius around each city centre, so a generous
    bound is correct here: this catches a city wired to the wrong coordinates or
    a transposed lon/lat, not a wide tram catchment.
    """

    def test_lines_are_near_their_city(self):
        with open(os.path.join(ROOT, "data", "research", "coords.json"), encoding="utf-8") as fh:
            coords = {c["slug"]: c for c in json.load(fh)}
        for slug, d in load_networks().items():
            c = coords.get(slug)
            if not c:
                continue
            pts = [p for ln in d["lines"] for path in ln["paths"] for p in path]
            if not pts:
                continue
            k = 111.0 * math.cos(math.radians(c["lat"]))
            with self.subTest(slug=slug):
                mlon = sum(p[0] for p in pts) / len(pts)
                mlat = sum(p[1] for p in pts) / len(pts)
                centroid_km = math.hypot((mlon - c["lon"]) * k, (mlat - c["lat"]) * 111.0)
                self.assertLess(centroid_km, 60,
                                f"{slug}: line centroid {centroid_km:.0f} km from the city centre")


class TestReadmeMatchesTheData(unittest.TestCase):
    """The README's counts are asserted against the files, not trusted.

    This is the test that would have caught "1,303 lines".
    """

    @classmethod
    def setUpClass(cls):
        cls.nets = load_networks()
        cls.text = readme()

    def claimed(self, pattern: str) -> int:
        m = re.search(pattern, self.text)
        self.assertIsNotNone(m, f"README no longer states a count matching {pattern!r}")
        return int(m.group(1).replace(",", ""))

    def test_system_count(self):
        self.assertEqual(self.claimed(r"\*\*([\d,]+) systems carry both line and station"),
                         len(self.nets))

    def test_line_count(self):
        actual = sum(len(d["lines"]) for d in self.nets.values())
        self.assertEqual(self.claimed(r"([\d,]+) lines and [\d,]+ stations"), actual)

    def test_station_count(self):
        actual = sum(len(d["stations"]) for d in self.nets.values())
        self.assertEqual(self.claimed(r"[\d,]+ lines and ([\d,]+) stations"), actual)


class TestMeasurementEnums(unittest.TestCase):
    """Both provenance enums resolve for every system, with nothing defaulting."""

    def test_every_measure_def_maps_to_the_enum(self):
        import csv
        from comparability import normalize_measure
        with open(os.path.join(ROOT, "data", "ridership", "system_rank.csv"),
                  newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                with self.subTest(slug=r["system_id"]):
                    normalize_measure(r["measure_def"])   # raises UnmappableMeasure

    def test_every_system_classifies_a_mode_scope(self):
        import csv
        import mode_scope
        with open(os.path.join(ROOT, "data", "ridership", "system_rank.csv"),
                  newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                with self.subTest(slug=r["system_id"]):
                    scope, _, _, _ = mode_scope.resolve(r["system_id"], r["system"], r["mode"])
                    self.assertIn(scope, mode_scope.ENUM)

    def test_mode_scope_overrides_are_well_formed(self):
        import csv
        import mode_scope
        path = os.path.join(ROOT, "data", "ridership", "mode_scope_overrides.csv")
        if not os.path.exists(path):
            self.skipTest("no reviewed overrides yet")
        known = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(NETWORKS, "*.json"))}
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows, "override file exists but is empty")
        for r in rows:
            with self.subTest(slug=r["slug"]):
                self.assertIn(r["slug"], known, "override names a system with no network file")
                self.assertIn(r["mode_scope"], mode_scope.ENUM)
                # SCHEMA.md: never a bare assertion -- a reviewed row shows its work.
                self.assertTrue(r["evidence"].strip(), "reviewed row carries no evidence")
                self.assertTrue(r["url"].strip(), "reviewed row carries no URL")


class TestPipelinesRun(unittest.TestCase):
    def test_comparability_audit_runs_clean(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "comparability.py")],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("201 systems", r.stdout)
        self.assertIn("numerator mode scope (axis 2)", r.stdout,
                      "axis 2 is no longer reported")

    def test_build_is_reproducible(self):
        """index.html must be exactly what data/ currently generates.

        Non-destructive: if the rebuild differs, the committed bytes are put
        back before failing, so a local run never leaves a half-updated page.
        """
        page = os.path.join(ROOT, "index.html")
        with open(page, "rb") as fh:
            committed = fh.read()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "tm_gen.py")],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        with open(page, "rb") as fh:
            rebuilt = fh.read()
        if rebuilt != committed:
            with open(page, "wb") as fh:
                fh.write(committed)
            self.fail(f"index.html is stale: data/ generates {len(rebuilt)} bytes, "
                      f"the committed page is {len(committed)}. Run tools/tm_gen.py and commit.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
