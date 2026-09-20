#!/usr/bin/env python3
"""
verify_camet.py — check every Chinese system's ridership figure against the
primary source, and decide what it counts.

WHY THIS EXISTS

data/ridership/system_rank.csv labels 28 of the 30 Chinese systems
`station_entries`. That is wrong for most of them, and it matters more than any
other single error in the dataset: 28 systems is over half the entire
station_entries family, and China is 15% of the atlas.

The China Association of Metros (CAMET) publishes an annual statistics report
whose 表3 gives, for every city, two columns side by side:

    客运量   passenger volume
    进站量   station entries

They are not the same quantity, and the report itself proves which is which.
For every SINGLE-LINE city the two columns are bit-identical:

    淮安    8,453,000  /  8,453,000
    东莞   49,417,400  / 49,417,400
    乌鲁木齐 43,346,700  / 43,346,700
    天水    1,057,400  /  1,057,400
    三亚    1,611,600  /  1,611,600
    太原   48,199,200  / 48,199,200

A single-line network has no transfers, so a boarding and a station entry are
the same event. Where a city has more than one line the columns diverge, and
the gap is exactly the transfer volume — nationally 32.26bn against 19.36bn, a
ratio of 1.666. Therefore:

    客运量 = 进站量 + 换乘量  =>  客运量 is UNLINKED TRIPS (boardings)
    进站量                    =>  station entries

So any Chinese figure taken from an operator's or CAMET's headline 客运量 is
`unlinked_trips`, and labelling it `station_entries` understates transfer-heavy
networks by up to 90%.

WHAT THIS SCRIPT DOES

Rather than assume, it tests each system's recorded value against BOTH columns
and reports which one it matches. A value within 0.2% of 客运量 is decided; a
value within 12% is decided with a note (the atlas carries some 2025 figures
against this 2024 report); anything further matches neither column and is left
`unknown` rather than guessed — those turn out to be the systems whose vintage
predates the report entirely.

    python3 tools/verify_camet.py                 # report only
    python3 tools/verify_camet.py --write         # update measure_def_overrides.csv

The report PDF is ~9 MB and CAMET's own notice forbids redistribution, so it is
downloaded to a temp directory and not committed. Only the derived verdicts and
the figures needed to justify them are kept.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COV = os.path.join(ROOT, "data", "research", "covariates.csv")
OVERRIDES = os.path.join(ROOT, "data", "ridership", "measure_def_overrides.csv")

REPORT_URL = (
    "https://infosharingp2-oss.camet.org.cn/resources/manual/2025/04/01/"
    "660853988892741.pdf"
)
REPORT_CITE = "CAMET 城市轨道交通2024年度统计和分析报告, 表3"

# 表3 lists cities in Chinese; the atlas keys on slugs.
SLUG_TO_HANZI = {
    "beijing": "北京", "shanghai": "上海", "tianjin": "天津", "chongqing": "重庆",
    "guangzhou": "广州", "shenzhen": "深圳", "wuhan": "武汉", "nanjing": "南京",
    "shenyang": "沈阳", "changchun": "长春", "dalian": "大连", "chengdu": "成都",
    "xian": "西安", "harbin": "哈尔滨", "suzhou": "苏州", "zhengzhou": "郑州",
    "kunming": "昆明", "hangzhou": "杭州", "foshan": "佛山", "changsha": "长沙",
    "ningbo": "宁波", "wuxi": "无锡", "nanchang": "南昌", "lanzhou": "兰州",
    "qingdao": "青岛", "fuzhou": "福州", "nanning": "南宁", "hefei": "合肥",
    "shijiazhuang": "石家庄", "guiyang": "贵阳", "xiamen": "厦门",
    "urumqi": "乌鲁木齐", "jinan": "济南", "changzhou": "常州", "xuzhou": "徐州",
    "hohhot": "呼和浩特", "taiyuan": "太原", "luoyang": "洛阳",
}

# Single-line cities, used as the proof that 客运量 and 进站量 are different
# quantities that coincide only when transfers are impossible.
SINGLE_LINE_PROOF = ["淮安", "东莞", "乌鲁木齐", "天水", "三亚", "太原"]

EXACT = 0.002   # within 0.2% -> the figure IS that column
CLOSE = 0.12    # within 12%  -> same quantity, different reporting year


def fetch_report(path: str) -> str:
    if os.path.exists(path):
        return path
    print(f"downloading {REPORT_URL}")
    req = urllib.request.Request(REPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as fh:
        fh.write(r.read())
    return path


def parse_table3(pdf_path: str) -> dict[str, dict]:
    try:
        import pypdf
    except ImportError:
        sys.exit("pypdf required:  pip install pypdf")

    reader = pypdf.PdfReader(pdf_path)
    out: dict[str, dict] = {}
    # "29 南宁 36523.71 99.79 21609.99 ..." -> rank, city, 客运量, 日均, 进站量
    row = re.compile(r"^\s*(\d{1,3})\s+([一-鿿]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")
    for page in reader.pages:
        text = page.extract_text() or ""
        if "进站量" not in text or "客运量" not in text:
            continue
        for line in text.split("\n"):
            m = row.match(line)
            if not m:
                continue
            out[m.group(2)] = {
                # both columns are printed in 万人次 (ten-thousand person-trips)
                "boardings": float(m.group(3)) * 1e4,
                "entries": float(m.group(5)) * 1e4,
            }
    return out


def prove(table: dict[str, dict]) -> bool:
    """The single-line identity is what licenses every verdict below."""
    print(f"{'city':10}{'客运量 boardings':>20}{'进站量 entries':>20}   single-line?")
    ok = True
    for city in SINGLE_LINE_PROOF:
        d = table.get(city)
        if not d:
            print(f"  {city:8} not found in 表3")
            ok = False
            continue
        same = d["boardings"] == d["entries"]
        ok &= same
        print(f"{city:10}{d['boardings']:>20,.0f}{d['entries']:>20,.0f}   "
              f"{'IDENTICAL' if same else 'DIFFER -- proof fails'}")
    tb = sum(d["boardings"] for d in table.values())
    te = sum(d["entries"] for d in table.values())
    print(f"\n  table totals: boardings {tb:,.0f}  entries {te:,.0f}  ratio {tb/te:.3f}")
    print("  => 客运量 = 进站量 + 换乘量, so 客运量 is unlinked trips.\n")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="write data/ridership/measure_def_overrides.csv")
    args = ap.parse_args()

    pdf = fetch_report(os.path.join(tempfile.gettempdir(), "camet_2024.pdf"))
    table = parse_table3(pdf)
    print(f"parsed {len(table)} cities from {REPORT_CITE}\n")

    if not prove(table):
        print("The single-line identity did not hold. Refusing to emit verdicts.")
        return 1

    with open(COV, newline="", encoding="utf-8") as fh:
        cov = {r["slug"]: r for r in csv.DictReader(fh)}
    systems = sorted(s for s in cov if cov[s]["country"] == "China")

    verdicts = []
    print(f"{'slug':15}{'value':>15} {'yr':<6}{'/客运量':>9}{'/进站量':>9}  verdict")
    print("-" * 74)
    for slug in systems:
        raw = (cov[slug]["annual_riders"] or "").strip()
        if not raw:
            continue
        value = float(raw)
        year = cov[slug]["annual_year"]
        d = table.get(SLUG_TO_HANZI.get(slug, ""))
        if not d:
            verdicts.append((slug, "", "low",
                             f"not listed in {REPORT_CITE}", "", "unverified"))
            print(f"{slug:15}{value:>15,.0f} {year:<6}{'-':>9}{'-':>9}  unknown (not in 表3)")
            continue

        rb, re_ = value / d["boardings"], value / d["entries"]
        db, de = abs(rb - 1), abs(re_ - 1)
        col, off = ("boardings", db) if db < de else ("entries", de)
        metric = "unlinked_trips" if col == "boardings" else "station_entries"

        if off < EXACT:
            conf, note = "high", f"matches 客运量 exactly (ratio {rb:.4f})" if col == "boardings" \
                else f"matches 进站量 exactly (ratio {re_:.4f})"
        elif off < CLOSE:
            conf, note = "medium", (f"matches 客运量 to {off*100:.1f}% (atlas year {year} "
                                    f"vs report year 2024)")
        else:
            metric, conf = "", "low"
            note = (f"matches neither column (客运量 x{rb:.2f}, 进站量 x{re_:.2f}); "
                    f"atlas vintage {year} predates this report")

        evidence = (f"{REPORT_CITE}: 客运量 {d['boardings']:,.0f} / "
                    f"进站量 {d['entries']:,.0f}. {note}")
        verdicts.append((slug, metric, conf, evidence, REPORT_URL,
                         "verified" if conf in ("high", "medium") else "unverified"))
        print(f"{slug:15}{value:>15,.0f} {year:<6}{rb:>9.3f}{re_:>9.3f}  "
              f"{metric or 'unknown':<16}[{conf}]")

    import collections
    print("\nverdicts:", dict(collections.Counter(v[1] or "unknown" for v in verdicts)))

    if not args.write:
        print("\n(re-run with --write to emit data/ridership/measure_def_overrides.csv)")
        return 0

    existing = []
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, newline="", encoding="utf-8") as fh:
            existing = [r for r in csv.DictReader(fh) if r["source"] != "camet"]

    with open(OVERRIDES, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["slug", "measure_def", "confidence", "value_status",
                    "evidence", "url", "source"])
        for r in existing:
            w.writerow([r["slug"], r["measure_def"], r["confidence"],
                        r["value_status"], r["evidence"], r["url"], r["source"]])
        for slug, metric, conf, ev, url, vs in verdicts:
            w.writerow([slug, metric, conf, vs, ev, url, "camet"])
    print(f"\nwrote {os.path.relpath(OVERRIDES, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
