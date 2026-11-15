# -*- coding: utf-8 -*-
"""G0 input fingerprint gate / manifest writer.

  python -X utf8 scripts/hash_manifest.py --check
  python -X utf8 scripts/hash_manifest.py --write   # only for an intentional release

The manifest covers rows + all V3 source files + the V9 reference/base.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "assets" / "golden" / "hashes.json"
FILES = [
    "assets/workbench/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html",
    "assets/data/_rows_all.json",
    "assets/data/_rows.json",
    "assets/source/v3.js",
    "assets/source/v3.css",
    "assets/source/v3-extra.css",
    "assets/source/v3-gold.css",
    "assets/source/echarts.min.js",
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def current() -> dict:
    out = {}
    for rel in FILES:
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit(f"MISSING {rel}")
        out[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    return {"version": "V9", "generated": "2026-11-06", "files": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    cur = current()
    if args.write:
        GOLD.parent.mkdir(parents=True, exist_ok=True)
        GOLD.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("WROTE", GOLD)
        print(json.dumps(cur, ensure_ascii=False, indent=2))
        return
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    bad = []
    for rel, meta in cur["files"].items():
        exp = gold["files"].get(rel)
        if not exp or exp.get("sha256") != meta["sha256"] or int(exp.get("bytes", -1)) != meta["bytes"]:
            bad.append(rel)
            print(f"DIFF {rel}\n  expected {exp}\n  actual   {meta}")
        else:
            print(f"OK   {rel} {meta['bytes']} {meta['sha256'][:12]}…")
    if bad:
        print(f"G0 FAIL: {len(bad)} file(s) changed", file=sys.stderr)
        raise SystemExit(1)
    print("G0 PASS: all input/source fingerprints match V9 manifest")


if __name__ == "__main__":
    main()
