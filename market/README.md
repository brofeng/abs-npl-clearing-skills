# market/ · 上架包与展示素材

本目录是**给 WorkBuddy 开放平台上传用**的成品，不要手改，由 `tools/build_market_package.py` 生成。

| 文件 | 体积 | 用途 |
|---|---|---|
| `abs-clearing-report-4.2.0.zip` | 1.93 MB | 技能一上架包（≤3 MB 硬上限） |
| `abs-workbench-1.0.0.zip` | 0.49 MB | 技能二上架包 |
| `skill-01-icon.png` | 3.4 KB | 技能一市场头像（512×512） |
| `skill-02-icon.png` | 3.2 KB | 技能二市场头像（512×512） |

## 重新生成

```bash
python -X utf8 tools/build_market_package.py
```

## 上传时填什么

见 [`../docs/01-上架WorkBuddy技能市场.md`](../docs/01-上架WorkBuddy技能市场.md)，
含两个技能的展示名、英文名、版本、分类、简介与避坑清单。

## 为什么比 skills/ 小这么多

市场包剔除了 PNG 像素基线与 V9 参考实现（共约 21 MB），方法与台账全量保留。
包内 `references/99-完整资产包获取.md` 说明了缺什么、怎么补。
