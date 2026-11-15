# -*- coding: utf-8 -*-
r"""Bridge one accepted single-project output into the multi-deal workbench row contract.

This is a *contract bridge*, not a second upstream PDF parser:
  project/02_提取数据/{metrics,payload}.json
    + project/03_报告产出/*_不良ABS穿透分析_v*.html
    + optional canonical _rows_all.json
  -> one normalized row JSON

Usage:
  python -X utf8 scripts/export_workbench_row.py \
    --project "E:\\path\\项目名" \
    --canonical "E:\path\_rows_all.json" \
    --out ".\workbench_row.json"

Exit codes:
  0 = row written (warnings allowed unless --strict)
  1 = contract failure (missing core input/field)
  2 = project path/type error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
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
REQUIRED = [
    "bank", "proj", "variety", "issue_date", "state", "life", "issue", "pool",
    "sec_rate", "sub_pct", "coupon", "recovery", "exp", "achieve", "dispose",
    "servicer", "fee", "sen_xirr", "sub_xirr", "mult", "year",
]


def die(msg: str, code: int = 1) -> None:
    print("ERROR:", msg, file=sys.stderr)
    raise SystemExit(code)


def read_json(path: Path) -> dict:
    if not path.is_file():
        die(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"invalid JSON {path}: {exc}")


def norm_name(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def num(v, default=None):
    try:
        if v is None or v == "":
            return default
        f = float(v)
        return f if f == f and abs(f) != float("inf") else default
    except Exception:
        return default


def first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def infer_bank(meta: dict) -> str | None:
    for key in ("originator_short", "originator", "issuer", "name"):
        s = str(meta.get(key) or "")
        for k, v in BANK_MAP.items():
            if k in s:
                return v
    return None


def find_report(project: Path) -> Path | None:
    out = project / "03_报告产出"
    if not out.is_dir():
        return None
    cands = sorted(out.glob("*_不良ABS穿透分析_v*.html"))
    if not cands:
        cands = sorted(out.glob("*.html"))
    # ignore build probes / assert dumps
    cands = [p for p in cands if not p.name.startswith("_")]
    return cands[-1] if cands else None


def assert_summary(project: Path) -> tuple[list, list]:
    p = project / "03_报告产出" / "_assert_single.json"
    if not p.is_file():
        return [], []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    fails, skips = [], []
    if isinstance(obj, dict):
        for k in ("fails", "fail", "FAIL", "errors"):
            if isinstance(obj.get(k), list):
                fails = obj[k]
                break
        for k in ("skips", "skip", "SKIP"):
            if isinstance(obj.get(k), list):
                skips = obj[k]
                break
        # common aggregate shape
        if not fails and isinstance(obj.get("failures"), list):
            fails = obj["failures"]
    return fails, skips


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--canonical", default="")
    ap.add_argument("--out", default="workbench_row.json")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        die(f"project directory not found: {project}", 2)

    metrics = read_json(project / "02_提取数据" / "metrics.json")
    payload = read_json(project / "02_提取数据" / "payload.json")
    meta = payload.get("meta") or {}
    pool = payload.get("pool") or {}
    report = find_report(project)

    canonical = None
    if args.canonical:
        cp = Path(args.canonical).expanduser().resolve()
        if cp.is_file():
            rows = read_json(cp)
            if isinstance(rows, list):
                name = norm_name(meta.get("display_name") or meta.get("name") or project.name)
                for r in rows:
                    if norm_name(r.get("proj")) == name:
                        canonical = dict(r)
                        break
            if canonical is None:
                print(f"WARN: canonical row not found for {meta.get('display_name') or project.name}", file=sys.stderr)
        else:
            print(f"WARN: canonical not found: {cp}", file=sys.stderr)

    issue = num(first(metrics.get("issue_total"), canonical and canonical.get("issue")))
    pool_total = num(first(metrics.get("pool_total"), canonical and canonical.get("pool")))
    sub_issue = num(first(metrics.get("sub_issue"), canonical and canonical.get("sub_issue")))
    recovery = num(first(metrics.get("recovery_rate"), canonical and canonical.get("recovery")))
    achieve = num(first(metrics.get("achieve_rate"), canonical and canonical.get("achieve")))
    exp = num(first(metrics.get("exp_rec_rate"), canonical and canonical.get("exp")))
    if exp is None and recovery is not None and achieve:
        exp = recovery / achieve

    bank = infer_bank(meta) or (canonical or {}).get("bank")
    variety = meta.get("variety") or (canonical or {}).get("variety")
    proj = meta.get("display_name") or meta.get("name") or project.name
    issue_date = meta.get("issue_date") or (canonical or {}).get("issue_date")
    state = (canonical or {}).get("state") or ("settled" if meta.get("terminate_date") else None)
    life = num(metrics.get("life_months"))
    if life is not None:
        life = int(round(life))

    fails, skips = assert_summary(project)
    if not fails and canonical:
        fails = canonical.get("fails") or []
    if not skips and canonical:
        skips = canonical.get("skips") or []

    row = dict(canonical or {})
    row.update({
        "bank": bank,
        "proj": proj,
        "variety": variety,
        "issue_date": issue_date,
        "legal": meta.get("legal_maturity") or row.get("legal"),
        "term": meta.get("terminate_date") or row.get("term"),
        "state": state,
        "life": life,
        "issue": issue,
        "pool": pool_total,
        "sec_rate": num(first(metrics.get("securitization_rate"), row.get("sec_rate"))),
        "sub_pct": (sub_issue / issue) if (sub_issue is not None and issue) else row.get("sub_pct"),
        "coupon": num(first(metrics.get("sen_coupon"), row.get("coupon"))),
        "recovery": recovery,
        "exp": exp,
        "achieve": achieve,
        "dispose": num(first(metrics.get("dispose_fee_rate"), row.get("dispose"))),
        "servicer": num(first(metrics.get("servicer_fee_rate"), row.get("servicer"))),
        "fee": num(first(metrics.get("fee_total_rate"), row.get("fee"))),
        "sen_xirr": num(first(metrics.get("sen_xirr"), row.get("sen_xirr"))),
        "sub_xirr": num(first(metrics.get("sub_xirr"), row.get("sub_xirr"))),
        "mult": num(first(metrics.get("sub_multiple"), row.get("mult"))),
        "n_loans": first(pool.get("n_loans"), row.get("n_loans")),
        "n_bor": first(pool.get("n_borrowers"), row.get("n_bor")),
        "avg_loan": num(first(pool.get("avg_loan_balance"), row.get("avg_loan"))),
        "wavg_od": num(first(pool.get("wavg_overdue_months"), row.get("wavg_od"))),
        "recovered": num(first(metrics.get("recovered"), row.get("recovered"))),
        "sen_issue": num(first(metrics.get("sen_issue"), row.get("sen_issue"))),
        "sub_issue": sub_issue,
        "line": LINE_MAP.get(str(variety or ""), row.get("line")),
        "year": str(issue_date or "")[:4] or row.get("year"),
        "fails": fails,
        "skips": skips,
        "report_html": str(report) if report else None,
    })

    missing = [k for k in REQUIRED if row.get(k) in (None, "", []) and k not in ("fails", "skips")]
    # allow null state for unclassified new projects only in non-strict mode
    if args.strict and missing:
        die("missing required fields: " + ", ".join(missing))

    # stable JSON for hashing
    text = json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"ROW_OK {row.get('bank')} | {row.get('proj')} | {row.get('variety')} | {row.get('issue_date')}")
    print(f"OUT {out} {len(text.encode('utf-8'))} bytes")
    print(f"SHA256 {h}")
    if missing:
        print("WARN missing: " + ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
