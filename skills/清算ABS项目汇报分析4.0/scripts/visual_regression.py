#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""visual_regression.py —— 黄金截图基线 / 像素回归

用法：
    # 1) 生成基线（改版后跑一次；31 张，约 3 分钟）
    <python> visual_regression.py --html <报告.html> --mode snapshot --out <golden/screens>

    # 2) 回归比对（DoD 门禁之一；不一致 EXIT=1）
    <python> visual_regression.py --html <报告.html> --mode verify --golden <golden/screens>

    # 只查某几个视图
    <python> visual_regression.py ... --only p0,p1,overview

判据：两图均缩放到固定宽度后，逐像素通道差 > 阈值即视为不同像素；
不同像素占比 > tol（默认 0.8%）判为「不一致」。这样能容忍抗锯齿/字体微差，
但能抓住布局位移、颜色变化、元素缺失。

依赖 Pillow（运行时自带）。
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageChops

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
WIN_W, WIN_H = 1600, 1400
VIEW_WAIT_MS = 900
SHOT_WIDTH = 800          # 比对前统一缩放宽度（降噪 + 提速）
CH_TOL = 18               # 单通道容差
PIX_TOL = 0.008           # 不同像素占比阈值


def find_edge():
    for p in EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("未找到 Edge，请用 --edge 指定")


def list_views(html_path: Path) -> list:
    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    vids = re.findall(r'class="sb-item"\s+data-view="([^"]+)"', txt)
    if not vids:
        vids = re.findall(r'data-view="([a-z][a-z0-9]*)"', txt)
    seen, out = set(), []
    for v in vids:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def shot(html_path: Path, vid: str, edge: str, out_png: Path):
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    inject = (
        "<script>setTimeout(function(){"
        f'var a=document.querySelector(\'.sb-item[data-view="{vid}"]\');'
        "if(a)a.click();"
        "},500);</script>"
    )
    tmp = Path(tempfile.mkdtemp(prefix="shot_")) / "v.html"
    tmp.write_text(html.replace("</body>", inject + "</body>", 1), encoding="utf-8")
    url = "file:///" + str(tmp).replace("\\", "/")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if out_png.exists():
        out_png.unlink()
    subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         f"--virtual-time-budget={VIEW_WAIT_MS + 9000}",
         f"--window-size={WIN_W},{WIN_H}", f"--screenshot={out_png}", url],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
    return out_png.exists()


def norm_img(p: Path) -> Image.Image:
    im = Image.open(p).convert("RGB")
    w, h = im.size
    nh = max(1, int(h * SHOT_WIDTH / w))
    return im.resize((SHOT_WIDTH, nh), Image.LANCZOS)


def diff_ratio(a: Path, b: Path):
    ia, ib = norm_img(a), norm_img(b)
    if ia.size != ib.size:
        return 1.0, f"尺寸不同 {ia.size} vs {ib.size}"
    diff = ImageChops.difference(ia, ib)
    px = diff.load()
    w, h = diff.size
    step = 1
    bad = tot = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, bl = px[x, y]
            tot += 1
            if r > CH_TOL or g > CH_TOL or bl > CH_TOL:
                bad += 1
    return (bad / tot if tot else 0.0), f"{bad}/{tot} 像素不同"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--mode", choices=["snapshot", "verify"], required=True)
    ap.add_argument("--out", help="snapshot 模式输出目录")
    ap.add_argument("--golden", help="verify 模式基线目录")
    ap.add_argument("--only", help="逗号分隔的视图 id 子集")
    ap.add_argument("--tol", type=float, default=PIX_TOL)
    ap.add_argument("--edge", default=None)
    args = ap.parse_args()

    edge = args.edge or find_edge()
    html = Path(args.html).resolve()
    if not html.exists():
        raise SystemExit(f"报告不存在: {html}")

    vids = list_views(html)
    if args.only:
        keep = set(x.strip() for x in args.only.split(","))
        vids = [v for v in vids if v in keep]
    print(f"视图 {len(vids)} 个")

    if args.mode == "snapshot":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        manifest = {}
        ok = 0
        for i, vid in enumerate(vids, 1):
            p = out / f"{vid}.png"
            if shot(html, vid, edge, p):
                manifest[vid] = {"sha256": sha(p), "bytes": p.stat().st_size}
                ok += 1
                print(f"  [{i}/{len(vids)}] {vid:<12} {p.stat().st_size:>8,} B")
            else:
                print(f"  [{i}/{len(vids)}] {vid:<12} ❌ 截图失败")
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n✅ 基线 {ok}/{len(vids)} 张 → {out}")
        return

    if not args.golden:
        raise SystemExit("verify 模式必须给 --golden")
    g = Path(args.golden)
    tmpd = Path(tempfile.mkdtemp(prefix="vshot_"))
    bad = []
    for i, vid in enumerate(vids, 1):
        gp = g / f"{vid}.png"
        if not gp.exists():
            print(f"  [{i}/{len(vids)}] {vid:<12} ⚠ 基线缺失，跳过")
            continue
        tp = tmpd / f"{vid}.png"
        if not shot(html, vid, edge, tp):
            bad.append((vid, 1.0, "截图失败"))
            print(f"  [{i}/{len(vids)}] {vid:<12} ❌ 截图失败")
            continue
        r, info = diff_ratio(gp, tp)
        flag = "✅" if r <= args.tol else "❌"
        if r > args.tol:
            bad.append((vid, r, info))
        print(f"  [{i}/{len(vids)}] {vid:<12} {flag} 差异 {r*100:6.3f}%  {info}")

    print()
    if bad:
        print(f"❌ {len(bad)} 个视图与基线不一致（阈值 {args.tol*100:.1f}%）：")
        for v, r, info in bad:
            print(f"   {v:<12} {r*100:.3f}%  {info}")
        sys.exit(1)
    print("✅ 视觉回归通过")


if __name__ == "__main__":
    main()
