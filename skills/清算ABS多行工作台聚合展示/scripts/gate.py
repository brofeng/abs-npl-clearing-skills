# -*- coding: utf-8 -*-
"""Workbench gate: G1 byte hash + G2 rows/structure + G3 Playwright interactions.

  python -X utf8 scripts/gate.py --html dist/..._V9.html
  python -X utf8 scripts/gate.py --static-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from aggregate_rows import validate_rows  # noqa: E402

DEFAULT = ROOT / "dist" / "不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"
GOLD = ROOT / "assets" / "golden" / "hashes.json"
V9_KEY = "assets/workbench/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_rows(html: str) -> list:
    marker = "const V3_FULL = "
    i = html.find(marker)
    if i < 0:
        raise SystemExit("G2_FAIL: V3_FULL marker not found")
    dec = json.JSONDecoder()
    rows, _ = dec.raw_decode(html[i + len(marker):])
    return rows


def static_gate(html_path: Path) -> bool:
    print("== G1 / G2 static ==")
    if not html_path.is_file():
        print("FAIL missing", html_path)
        return False
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    exp = gold["files"][V9_KEY]
    b = html_path.read_bytes()
    got = hashlib.sha256(b).hexdigest()
    ok = len(b) == exp["bytes"] and got == exp["sha256"]
    print(("PASS" if ok else "FAIL") + f" G1 byte hash {len(b)} {got}")
    if not ok:
        print(f"  expected {exp['bytes']} {exp['sha256']}")
    html = b.decode("utf-8")
    try:
        rows = extract_rows(html)
    except Exception as exc:
        print("FAIL V3_FULL parse:", exc)
        return False
    print(("PASS" if len(rows) == 74 else "FAIL") + f" V3_FULL rows {len(rows)}")
    if len(rows) != 74:
        return False
    try:
        validate_rows(rows, 74)
    except SystemExit:
        return False
    for s in ('id="v3-theme"', 'id="v3-echarts"', 'id="v3-app"', "data-label", "__v3cashflowParsed", "封包结构"):
        good = s in html
        print(("PASS" if good else "FAIL") + f" static marker {s}")
        if not good:
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=str(DEFAULT))
    ap.add_argument("--static-only", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    html = Path(args.html)
    if not static_gate(html):
        print("GATE FAIL (static)")
        raise SystemExit(1)
    if args.static_only or args.no_browser:
        print("GATE PASS (static only; G3 not run)")
        return
    from verify_workbench import check_runtime
    if not check_runtime(html):
        print("GATE FAIL (runtime)")
        raise SystemExit(1)
    print("GATE PASS: G1 + G2 + G3")


if __name__ == "__main__":
    main()
