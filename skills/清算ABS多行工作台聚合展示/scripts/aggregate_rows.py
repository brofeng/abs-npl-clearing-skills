# -*- coding: utf-8 -*-
"""Aggregate accepted single-project outputs into the 74-row workbench contract.

Two modes:
  A. Validate the canonical 74 rows:
       python -X utf8 scripts/aggregate_rows.py --check --rows assets/data/_rows_all.json --expect-count 74
  B. Scan project folders and write a new rows file (canonical merge optional):
       python -X utf8 scripts/aggregate_rows.py --projects-root "<root>" \
         --canonical assets/data/_rows_all.json --out dist/_rows_all.json

The bridge does NOT parse PDFs. It consumes the single-project pipeline's
02_提取数据/{metrics,payload}.json and optional _assert_single.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

BANK_MAP = {
    "中信": "中信银行", "中信银行": "中信银行",
    "招商": "招商银行", "招商银行": "招商银行",
    "建设": "建设银行", "建设银行": "建设银行",
    "兴业": "兴业银行", "兴业银行": "兴业银行",
    "农业": "农业银行", "农业银行": "农业银行", "农行": "农业银行",
}
LINE_MAP = {
    "信用卡不良": "信用卡",
    "个人经营不良": "个人经营",
    "个人消费不良": "个人消费",
    "住房抵押不良": "住房抵押",
}
CORE = [
    "bank", "proj", "variety", "issue_date", "state", "life", "issue", "pool",
    "sec_rate", "sub_pct", "coupon", "recovery", "exp", "achieve", "dispose",
    "servicer", "fee", "sen_xirr", "sub_xirr", "mult", "year",
]


def die(msg: str, code: int = 1) -> None:
    print("ERROR:", msg, file=sys.stderr)
    raise SystemExit(code)


def read_json(p: Path):
    if not p.is_file():
        die(f"missing {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"invalid JSON {p}: {exc}")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def num(v, default=None):
    try:
        if v is None or v == "":
            return default
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def infer_bank(meta: dict):
    for key in ("originator_short", "originator", "issuer", "name"):
        s = str(meta.get(key) or "")
        for k, v in BANK_MAP.items():
            if k in s:
                return v
    return None


def assert_summary(project: Path):
    p = project / "03_报告产出" / "_assert_single.json"
    if not p.is_file():
        return [], []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    fails = obj.get("fails") if isinstance(obj, dict) else []
    skips = obj.get("skips") if isinstance(obj, dict) else []
    return (fails if isinstance(fails, list) else []), (skips if isinstance(skips, list) else [])


def project_row(project: Path, canonical: dict | None) -> dict:
    metrics = read_json(project / "02_提取数据" / "metrics.json")
    payload = read_json(project / "02_提取数据" / "payload.json")
    meta = payload.get("meta") or {}
    pool = payload.get("pool") or {}
    canonical = canonical or {}
    issue = num(first(metrics.get("issue_total"), canonical.get("issue")))
    pool_total = num(first(metrics.get("pool_total"), canonical.get("pool")))
    sub_issue = num(first(metrics.get("sub_issue"), canonical.get("sub_issue")))
    recovery = num(first(metrics.get("recovery_rate"), canonical.get("recovery")))
    achieve = num(first(metrics.get("achieve_rate"), canonical.get("achieve")))
    exp = num(first(metrics.get("exp_rec_rate"), canonical.get("exp")))
    if exp is None and recovery is not None and achieve:
        exp = recovery / achieve
    variety = meta.get("variety") or canonical.get("variety")
    proj = meta.get("display_name") or meta.get("name") or project.name
    issue_date = meta.get("issue_date") or canonical.get("issue_date")
    state = canonical.get("state")
    if not state:
        state = "settled" if str(meta.get("terminate_date") or "") else "open"
    life = num(metrics.get("life_months"))
    if life is not None:
        life = int(round(life))
    fails, skips = assert_summary(project)
    if not fails:
        fails = canonical.get("fails") or []
    if not skips:
        skips = canonical.get("skips") or []

    row = dict(canonical)
    row.update({
        "bank": infer_bank(meta) or canonical.get("bank"),
        "proj": proj,
        "variety": variety,
        "issue_date": issue_date,
        "legal": meta.get("legal_maturity") or canonical.get("legal"),
        "term": meta.get("terminate_date") or canonical.get("term"),
        "state": state,
        "life": life if life is not None else canonical.get("life"),
        "issue": issue,
        "pool": pool_total,
        "sec_rate": num(first(metrics.get("securitization_rate"), canonical.get("sec_rate"))),
        "sub_pct": (sub_issue / issue) if (sub_issue is not None and issue) else canonical.get("sub_pct"),
        "coupon": num(first(metrics.get("sen_coupon"), canonical.get("coupon"))),
        "recovery": recovery,
        "exp": exp,
        "achieve": achieve,
        "dispose": num(first(metrics.get("dispose_fee_rate"), canonical.get("dispose"))),
        "servicer": num(first(metrics.get("servicer_fee_rate"), canonical.get("servicer"))),
        "fee": num(first(metrics.get("fee_total_rate"), canonical.get("fee"))),
        "sen_xirr": num(first(metrics.get("sen_xirr"), canonical.get("sen_xirr"))),
        "sub_xirr": num(first(metrics.get("sub_xirr"), canonical.get("sub_xirr"))),
        "mult": num(first(metrics.get("sub_multiple"), canonical.get("mult"))),
        "n_loans": first(pool.get("n_loans"), canonical.get("n_loans")),
        "n_bor": first(pool.get("n_borrowers"), canonical.get("n_bor")),
        "avg_loan": num(first(pool.get("avg_loan_balance"), canonical.get("avg_loan"))),
        "wavg_od": num(first(pool.get("wavg_overdue_months"), canonical.get("wavg_od"))),
        "recovered": num(first(metrics.get("recovered"), canonical.get("recovered"))),
        "sen_issue": num(first(metrics.get("sen_issue"), canonical.get("sen_issue"))),
        "sub_issue": sub_issue,
        "line": LINE_MAP.get(str(variety or ""), canonical.get("line")),
        "year": str(issue_date or "")[:4] or canonical.get("year"),
        "fails": fails,
        "skips": skips,
    })
    return row


def check_row(r: dict) -> list[str]:
    bad = []
    open_optional = {"sub_xirr", "mult"} if r.get("state") == "open" else set()
    for k in CORE:
        if r.get(k) in (None, "") and k not in open_optional:
            bad.append(f"missing {k}")
    try:
        d = date.fromisoformat(str(r.get("issue_date")))
        t = r.get("term")
        if t:
            td = date.fromisoformat(str(t))
            if td < d:
                bad.append("term < issue_date")
    except Exception:
        bad.append("bad date")
    for k in ("recovery", "sec_rate", "sub_pct", "coupon", "dispose", "servicer", "fee"):
        v = r.get(k)
        if v is not None and not (0 <= float(v) <= 1):
            bad.append(f"{k} out of 0..1")
    if r.get("achieve") is not None and not (0 <= float(r["achieve"]) <= 3):
        bad.append("achieve out of 0..3")
    if r.get("life") is not None and float(r["life"]) <= 0:
        bad.append("life <= 0")
    issue, pool, sub = r.get("issue"), r.get("pool"), r.get("sub_issue")
    try:
        if issue and pool and abs(float(r["sec_rate"]) - float(issue) / float(pool)) > 1e-6:
            bad.append("sec_rate != issue/pool")
        if issue and sub is not None and abs(float(r["sub_pct"]) - float(sub) / float(issue)) > 1e-6:
            bad.append("sub_pct != sub_issue/issue")
    except Exception:
        bad.append("formula non-numeric")
    try:
        if r.get("recovered") is not None and issue and abs(float(r["recovery"]) - float(r["recovered"]) / float(pool)) > 1e-6:
            bad.append("recovery != recovered/pool")
        if r.get("exp") and abs(float(r["achieve"]) - float(r["recovery"]) / float(r["exp"])) > 2e-3:
            bad.append("achieve != recovery/exp")
    except Exception:
        bad.append("ratio formula non-numeric")
    if r.get("fails"):
        bad.append(f"fails non-empty ({len(r['fails'])})")
    return bad


def validate_rows(rows: list, expect_count: int = 0) -> None:
    if not isinstance(rows, list):
        die("rows must be a list")
    if expect_count and len(rows) != expect_count:
        die(f"row count {len(rows)} != {expect_count}")
    names = [norm(r.get("proj")) for r in rows]
    if len(set(names)) != len(names):
        die("duplicate proj")
    if any(not n for n in names):
        die("empty proj")
    bad = []
    for i, r in enumerate(rows):
        errs = check_row(r)
        if errs:
            bad.append((i, r.get("proj"), errs))
    if bad:
        for i, p, errs in bad[:20]:
            print(f"ROW_FAIL[{i}] {p}: " + "; ".join(errs), file=sys.stderr)
        die(f"{len(bad)} row(s) failed validation")
    banks = {}
    states = {}
    for r in rows:
        banks[r.get("bank")] = banks.get(r.get("bank"), 0) + 1
        states[r.get("state")] = states.get(r.get("state"), 0) + 1
    print(f"ROWS_OK {len(rows)} | banks {banks} | states {states}")
    print(f"YEARS {dict(sorted({y: sum(1 for r in rows if str(r.get('year')) == y) for y in set(str(r.get('year')) for r in rows)}.items()))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects-root", default="")
    ap.add_argument("--canonical", default="")
    ap.add_argument("--rows", default="")
    ap.add_argument("--out", default="dist/_rows_all.json")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--expect-count", type=int, default=0)
    ap.add_argument("--include-new", action="store_true", help="include project dirs not present in --canonical (new dataset)")
    args = ap.parse_args()

    if args.check and args.rows:
        rows = read_json(Path(args.rows))
        validate_rows(rows, args.expect_count or 0)
        print("CHECK PASS")
        return

    if not args.projects_root:
        die("--projects-root or --check --rows is required", 2)
    root = Path(args.projects_root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}", 2)
    canon = {}
    if args.canonical:
        cp = Path(args.canonical).expanduser().resolve()
        if cp.is_file():
            for r in read_json(cp):
                canon[norm(r.get("proj"))] = r
        else:
            print(f"WARN canonical not found: {cp}", file=sys.stderr)

    projects = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if (d / "02_提取数据" / "metrics.json").is_file() and (d / "02_提取数据" / "payload.json").is_file():
            projects.append(d)
    if not projects:
        die(f"no projects with 02_提取数据/metrics.json + payload.json under {root}")

    rows = []
    for p in projects:
        payload = read_json(p / "02_提取数据" / "payload.json")
        meta = payload.get("meta") or {}
        name = norm(meta.get("display_name") or meta.get("name") or p.name)
        if canon and not args.include_new and name not in canon:
            print(f"SKIP not in canonical: {p.name} ({meta.get('display_name') or ''})", file=sys.stderr)
            continue
        rows.append(project_row(p, canon.get(name)))
    rows.sort(key=lambda r: (str(r.get("issue_date") or ""), str(r.get("proj") or "")))

    bad = []
    for r in rows:
        errs = check_row(r)
        if errs:
            bad.append((r.get("proj"), errs))
    if bad:
        for p, errs in bad[:20]:
            print(f"ROW_FAIL {p}: " + "; ".join(errs), file=sys.stderr)
        if args.strict:
            die(f"{len(bad)} row(s) failed validation")
        print(f"WARN {len(bad)} row(s) failed validation (non-strict)", file=sys.stderr)

    text = json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"OUT {out} {len(text.encode('utf-8'))} bytes")
    print(f"SHA256 {h}")
    validate_rows(rows, args.expect_count or 0)


if __name__ == "__main__":
    main()
