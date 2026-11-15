# NPL ABS Clearing Analysis — Agent Skills

> Turn disclosed Chinese interbank NPL securitisation documents (prospectus, trustee report,
> liquidation report, rating report) into **reproducible, gated, deliverable** deal-level
> deep-dive reports and multi-deal workbenches.
>
> Two WorkBuddy Agent Skills following the open `SKILL.md` convention; also loadable by
> Claude Code, Codex and other tools that support the same convention.

| Item | Value |
|---|---|
| Skill 1 | NPL ABS Clearing Report Analysis · **v4.2.0** |
| Skill 2 | NPL ABS Multi-Deal Workbench Builder · **v1.0.0** |
| Validation | **86 deals**, 4 banks, zero gate failures |
| Reference build | **74 deals / 5 banks / 13 ECharts + 1 cash-flow board** |
| Reproducibility | Deal report reproduced **byte-for-byte** (205,040 B) |
| License | MIT |

## What it does

**One line:** turn clearing-period NPL ABS documents (prospectus, trustee, liquidation and rating reports) into reproducible, gated, deliverable single-deal deep-dive reports and multi-deal workbenches.

**Who it is for**

- Special-situations, investment-banking, research and risk teams at brokers, banks and AMCs;
- analysts tracking NPL ABS performance, computing liquidation-period recoveries, or running post-mortems on deals;
- anyone who needs a like-for-like cross-deal comparison for management or investors, fast.

**Four things it does for you**

| Step | What you would normally do | What the skill gives you |
|---|---|---|
| Extraction | Copy figures out of four document types by hand, reconcile line by line, fight scanned-page coordinates | `scripts/pipeline/` produces `payload.json` with scanned-page coordinate recovery and per-line reconciliation; the extraction rules live in code |
| Reporting | Build an eight-section report and recompute every metric | Eight-section HTML report: securitisation ratio, disposal cost ratio, recovery rate, target achievement, senior/subordinated XIRR and XNPV, clean-up call, trust wind-up tests, cash-distribution waterfall, peer percentile |
| Aggregation | Stitch N reports into one table, then hand-build slicers and charts | Single-file workbench: slicers, multi-select, bank × product matrix, four-quadrant view, cash-flow board, report viewer, export / print (reference: 74 deals / 5 banks / 13 charts) |
| Acceptance | Re-check numbers by hand, never fully sure | Three-level gates: G1 byte identity, G2 96 data assertions, G3 137–144 interaction assertions — fail a gate, ship nothing |

**Why it is different** — most "financial analysis skills" are a prompt plus a table style. This is a production line with gates: the same input rebuilds to byte-identical output; any number change must pass the data and interaction assertions; a 12-item anti-pattern ledger and a four-bank style-divergence ledger capture real defects whose signature is *gates pass, totals are right, charts are self-consistent, and every detail is wrong*; and the counting conventions are written down instead of learned by trial and error.

**A full Chinese version of this document is in [README.md](README.md).**

## Why it is different

1. **Executable pipeline, not a prompt template** — PDF → `payload.json` with OCR coordinate
   restoration and line-by-line reconciliation against the trustee statements.
2. **Three-level gates** — G1 byte-level reproducibility, G2 data (96 assertions),
   G3 interaction (137–144 semantic assertions). Failing any gate blocks delivery.
3. **Anti-pattern ledger** — 12 real defects whose shared signature is *gates pass, totals
   correct, charts self-consistent, every detail wrong*. Each has exactly one cure.
4. **Style-divergence ledger** — three liquidation-report styles (Deloitte / KPMG / trust prose),
   two conventions for subordinated fixed funding cost, plus ordering keys, cumulative-period
   exclusions and opposite-direction recovery forecasts.
5. **Hard rule** — a deal that fails G1/G2/G3 never enters the aggregated workbench.

## Layout

```text
skills/清算ABS项目汇报分析4.0/            Skill 1 — single deal
skills/清算ABS多行工作台聚合展示/          Skill 2 — N deals workbench
market/                                 ≤3MB upload packages + 512×512 icons
docs/                                   business-flow notes and marketplace listing copy
```

Full documentation is in Chinese (`README.md`); the skills themselves, gate scripts and
directories are readable without knowing Chinese.

## Quick start

```bash
git clone https://github.com/brofeng/abs-npl-clearing-skills.git
# copy skills/<name>/ into ~/.workbuddy/skills/<name>/
cd ~/.workbuddy/skills/清算ABS多行工作台聚合展示
python -X utf8 scripts/build_workbench.py --check
```

Expected output: 11,385,763 B, SHA256 `8ae21fd0…`.

## Scope and disclaimer

No original project PDFs are included. Nothing here is investment advice, and the repository
contains no non-public institutional data, client information or internal material.
Users are responsible for ensuring their data sourcing complies with their own institution's
policies and applicable law.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
