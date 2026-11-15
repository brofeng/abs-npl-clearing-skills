# -*- coding: utf-8 -*-
"""Build V9 from package assets and enforce the byte-level golden gate.

Usage:
  python -X utf8 scripts/build_workbench.py --check
  python -X utf8 scripts/build_workbench.py --allow-drift   # only after intentional release
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from inject_v3 import BASE, ROWS, OUT, inject  # noqa: E402

GOLD = ROOT / "assets" / "golden" / "hashes.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--rows", default=str(ROWS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--allow-drift", action="store_true")
    args = ap.parse_args()

    info = inject(Path(args.base), Path(args.rows), Path(args.out), quiet=False)
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    key = "assets/workbench/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"
    expected = gold["files"][key]
    ok = info["sha256"] == expected["sha256"] and info["bytes"] == expected["bytes"]
    print("G1_EXPECTED", expected["bytes"], expected["sha256"])
    print("G1_ACTUAL  ", info["bytes"], info["sha256"])
    print("G1", "PASS" if ok else "FAIL")
    if not ok:
        print("G1_FAIL: output is not byte-identical to V9. Inspect source/rows/newlines.", file=sys.stderr)
        if not args.allow_drift:
            raise SystemExit(1)
        print("G1_DRIFT_ALLOWED: intentional release; update golden and version index.", file=sys.stderr)
    if args.check and not ok and not args.allow_drift:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
