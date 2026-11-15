# 14 · 复刻验收 DoD（Definition of Done）

> **这份文件解决的核心问题**：为什么别的 agent 用这个 skill 做出来"不像"。
>
> **答案：不是代码问题，是流程问题。** 本技能的 `scripts/v2/` 代码是**确定性**的——
> 实测在同一环境下构建，产物与基线 **SHA256 字节级一致**。
> 所以复刻失败一定发生在：**没用这套代码** / **漏跑模块** / **自己重写了一部分** / **没验证**。

---

## 一、铁律（不可协商）

### 铁律 1：**直接运行 `scripts/v2/`，不要重写模块**

❌ 错误做法：读技能文档 → 理解方法论 → 自己写一套"类似"的实现
✅ 正确做法：`setup_workspace.py` 还原 → 跑 `build_v2.py` → 产物哈希对得上

**原因**：脚本 26 万行字符级的 CSS/JS 里，藏着大量不写在文档里的细节——
精确到 0.5px 的间距、`scope_css` 的三个坑、标签配平修复、图表重绘时机……
**任何手工重写都会漂移**，而且是用户一眼就看得出来的漂移。

### 铁律 2：**不要改 `window-size`**

无头浏览器必须 `--window-size=1600,1400`。
响应式断点（1180 / 900 / 767）会改变栅格列数、卡片高度、字号，
**换个窗口尺寸，视觉就不是"那张图"了**。

### 铁律 3：**交付前必须跑 `verify_repro.py` 并 EXIT=0**

不跑 = 不知道对不对。跳过验证的交付视为未完成。

### 铁律 4：**不要为了让门禁通过而改基线**

基线是"用户已经验收过的样子"。改基线 = 宣布新样子才对。
**只有用户明确要求改版时**才更新基线，且必须在 README 写明变更原因。

---

## 二、标准复刻流程（5 步）

```bash
# ── 步 0：环境 ──
#   用 load_workspace_dependencies 拿 python 路径；不要 pip install
#   Edge 路径：C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe

# ── 步 1：还原工作区（skill 自带全部资产，不依赖原项目目录）──
<python> <skill>/scripts/setup_workspace.py --check      # 先看
<python> <skill>/scripts/setup_workspace.py             # 还原到 E:\不良ABS穿透研究
#   换盘/换机：加 --home D:\NPL_ABS  或 设环境变量 NPL_ABS_HOME

# ── 步 2：数据门控（确认字段边界）──
<python> <skill>/scripts/selfcheck_data.py \
         --payload E:\不良ABS穿透研究\清算28单_单项目穿透\_校验件\payload.json

# ── 步 3：构建（不要手改模块）──
<python> <skill>/scripts/v2/build_v2.py

# ── 步 4：一键复刻验收（**这一步是 DoD**）──
<python> <skill>/scripts/verify_repro.py \
         --html E:\不良ABS穿透研究\清算28单_不良ABS分析\清算28单_不良ABS穿透分析报告_v11.html

# ── 步 5（可选）：视觉回归 ──
<python> <skill>/scripts/verify_repro.py --html <同上> --visual
```

**步 4 通过标志**：
```
G1 哈希门禁
  期望 f5cc4529...a39fb  (4,013,112 B, v11)
  实得 f5cc4529...a39fb  (4,013,112 B)
✅ G1 通过：产物与基线字节级一致（最强保证，跳过 G2/G3）

✅ DoD 通过：可以交付
```

---

## 三、门禁说明（三级）

| 级别 | 手段 | 强度 | 耗时 | 说明 |
|---|---|---|---|---|
| **G1 哈希** | SHA256 比对 | ⭐⭐⭐⭐⭐ 字节级 | 1 秒 | 最严格；通过即可交付 |
| **G2 指纹** | 逐视图比对 版式+文案+字号 | ⭐⭐⭐⭐ 语义级 | ~40 秒 | 定位"哪一行/哪个尺寸"不对 |
| **G3 视觉** | 31 张截图像素比对 | ⭐⭐⭐ 视觉级 | ~3 分钟 | 抓 G2 抓不到的（抗锯齿外的视觉差） |

**G1 不过不一定是错**——可能只是环境差异（Edge 版本、字体）。
此时看 G2 差异：若差异集中在字体相关项（`fonts`、`heights` 小偏移），
说明是环境噪声；若差异集中在 `sections`/`text`/`tr`/`svg`，说明**真的改错了**。

---

## 四、常见失败与定位

| G2 报什么 | 说明什么 | 怎么修 |
|---|---|---|
| `sections` 不一致 | 板块标题或顺序变了 | 检查是否用了旧版 `30_compare.py` |
| `text` 第 N 行不一致 | 文案变了（最常见） | 对比基线该行，检查 `70_wording.py` 是否被改 |
| `tr` / `svg` / `cards` 数量不一致 | 模块漏跑或重复跑 | 看 `build_v2.py` 的 `load_module` 日志（应 7 模块全 ✅） |
| `gridCols` 变了 | 响应式被触发 | 检查 `--window-size` |
| `heights` 大范围变 | 布局塌了 | 检查是否有模块 HTML 标签不配平（build 会打 ⚠ 警告） |
| `fonts` 分布变 | 图表重绘逻辑变了 | 检查 `50_charts.py`/`60_assets.py` 是否被改 |
| `detailsOpen` > 0 | 折叠块默认展开了 | 检查 `40_audit.py` 的 `<details>` 有没有 `open` |

---

## 五、Agent 交接清单

任何 agent 接手本任务，**开工前必须回答**：

- [ ] 我用的是 skill 自带的 `scripts/v2/`，还是自己重写？→ **必须是自带**
- [ ] 我跑 `setup_workspace.py --check` 了吗？→ 必须全 ✅
- [ ] 我跑 `selfcheck_data.py` 了吗？→ 确认字段边界（3 个字段不存在！）
- [ ] 构建日志里 7 个模块是不是全 ✅？→ 缺一个都不行
- [ ] 我跑 `verify_repro.py` 了吗？EXIT 是 0 吗？
- [ ] 如果 G2 不过：我是"修实现"还是"打算改基线"？→ **修实现**

**交付时必须附**：
```
构建：7/7 模块 ✅  产物 4,013,112 B
G1: f5cc4529...a39fb  ✅
G2: 0 处差异  ✅
G3: 31/31 视图 ≤0.8% ✅（如跑了）
```

---

## 六、什么时候可以改基线

只有以下情况：

1. 用户**明确要求**改版（例："把 03 改成票面排序条形"）
2. 修了一个**用户认可的 bug**（例：担保方式异常备注丢失 → 补回）
3. 上游数据更新（新一期 payload）

**改基线流程**：
```bash
<python> scripts/v2/build_v2.py
<python> scripts/probe_report.py --html <新产物> --mode extract --out assets/golden/report_spec.json
<python> scripts/gen_layout_doc.py --spec assets/golden/report_spec.json --out references/12-版式像素规格.md
<python> scripts/visual_regression.py --html <新产物> --mode snapshot --out assets/golden/screens
# 手写新 SHA256 到 assets/golden/report.sha256
# 在 README_<版本>_精修版说明.md 写明：改了什么、为什么改
```

**未写 README 说明的基线更新，一律视为回归。**
