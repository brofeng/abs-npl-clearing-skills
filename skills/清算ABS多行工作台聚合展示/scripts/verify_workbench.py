# -*- coding: utf-8 -*-
"""G3 interaction gate for the V9 workbench. Requires Playwright + Microsoft Edge.

  python -X utf8 scripts/verify_workbench.py --html dist/..._V9.html
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "dist" / "不良ABS多行工作台_策略与投资人回报_尊享版_V9.html"


def check_runtime(html: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print("G3_SKIP: playwright not installed:", exc, file=sys.stderr)
        raise SystemExit(2)

    url = html.resolve().as_uri()
    errors = []
    failures = []

    def need(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
        page.on("console", lambda m: errors.append(("console", m.text)) if m.type == "error" else None)
        page.goto(url, wait_until="load", timeout=90000)
        page.wait_for_timeout(2200)

        need(page.evaluate("() => window.__v3charts.length") == 13, "13 ECharts")
        need(page.evaluate("() => window.__v3cashflowParsed") == 74, "cashflow parsed 74")
        need(page.locator(".cf-row").count() == 8, "cashflow board 8 rows")
        need(page.locator(".v3-pair").count() == 6, "6 paired rows")
        need("74" in page.locator('.kpi [data-kpi="count"]').inner_text(), "initial KPI 74")
        need("封包结构" in page.locator("#s5 h2").inner_text(), "s5 封包 typo fixed")
        need("SHA256" not in page.locator("#view-cmp header.hero .lead").inner_text(), "hero no technical SHA")
        ml = page.evaluate("""() => window.__v3charts.filter(c => {
          const o = c.getOption();
          return (o.series || []).some(s => s.markLine && s.markLine.data && s.markLine.data.length >= 2);
        }).length""")
        need(ml == 6, "6 scatter quadrants (x/y medians)")

        gap = page.evaluate("""() => {
          const g = document.querySelector('#s3 .grid2');
          const c = document.getElementById('v3-cashflow-card');
          return g && c ? Math.round(c.getBoundingClientRect().top - g.getBoundingClientRect().bottom) : -1;
        }""")
        need(gap == 14, f"cashflow gap 14px (got {gap})")

        # single select
        page.locator('#view-cmp .filterbar .fb-chip[data-k="variety"][data-v="信用卡不良"]').click()
        page.wait_for_timeout(700)
        need("54" in page.locator('.kpi [data-kpi="count"]').inner_text(), "single slice credit 54")
        page.locator("#v3-pill button").click()
        page.wait_for_timeout(700)
        need("74" in page.locator('.kpi [data-kpi="count"]').inner_text(), "clear back 74")

        # Ctrl multi: credit + personal consumption
        page.locator('#view-cmp .filterbar .fb-chip[data-k="variety"][data-v="信用卡不良"]').click()
        page.keyboard.down("Control")
        page.locator('#view-cmp .filterbar .fb-chip[data-k="variety"][data-v="个人消费不良"]').click()
        page.keyboard.up("Control")
        page.wait_for_timeout(700)
        n = page.evaluate("() => (window.__slice.varieties || []).length")
        need(n == 2, f"Ctrl multi 2 varieties (got {n})")
        page.locator("#v3-pill button").click()
        page.wait_for_timeout(600)

        # cashflow row -> bank view -> back
        page.locator("#v3-cashflow-card").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator(".cf-row").first.click()
        page.wait_for_timeout(700)
        view_id = page.evaluate("() => document.querySelector('.view:not(.hidden)').id")
        need(view_id.startswith("view-bank-"), f"cashflow row opens bank view (got {view_id})")
        page.locator('nav a.nv[data-view="cmp"]').first.click()
        page.wait_for_timeout(500)
        if page.locator("#v3-pill button").count():
            page.locator("#v3-pill button").click()
            page.wait_for_timeout(500)

        # bank page + table view
        page.locator('nav a.nv[data-view="bank-建设银行"]').first.click()
        page.wait_for_timeout(500)
        need(page.evaluate("() => document.querySelector('.view:not(.hidden)').id") == "view-bank-建设银行", "bank page opens")
        page.locator('nav a.nv[data-view="cmp"]').first.click()
        page.wait_for_timeout(400)
        page.locator('a.nv[data-view="table"]').first.click()
        page.wait_for_timeout(500)
        need(page.locator("#view-table").is_visible(), "table view opens")
        page.locator('nav a.nv[data-view="cmp"]').first.click()
        page.wait_for_timeout(400)

        # V9 is desktop-first; <900px single-column visual is supported,
        # but the original shell has deliberate off-canvas drawers. Do not gate document.scrollWidth.

        browser.close()

    if errors:
        print("JS_ERRORS:", errors[:10])
        failures.append("JS errors")
    print("G3", "PASS" if not failures else "FAIL")
    return not failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=str(DEFAULT))
    args = ap.parse_args()
    ok = check_runtime(Path(args.html))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
