# UI 回归（四档宽度）· QA 严过关

生成时间：2026-09-22 17:45:11

## B 段逐条

| 编号 | 断言 | 结果 |
|---|---|---|
| B1 | 面板唯一/侧栏29 | PASS |
| B2 | ⑤节+矩阵+⑦4卡+⑤2卡 | PASS |
| B3 | 四档无溢出+无裁切 | PASS |
| B4 | 空卡0/超大空白0 | PASS |
| B5 | 无undefined/NaN/星号 | PASS |
| B6 | console error 0 | PASS |
| B7 | 默认折叠态 | PASS |
| B8 | data-* 全覆盖 | PASS |
| B9 | data-* 全精度 | PASS |

## C 段：交互可见性（补「白屏」结构性缺陷；须在渲染可见前提下验证）

| 编号 | 断言 | 结果 |
|---|---|---|
| C1 | 键完整性（data-view 集 == .view id 去前缀集；各29） | PASS |
| C2 | 首屏非空且可见（.view.on 恰1；H>200；text>500） | PASS |
| C3 | 逐项点击可见性（29×；目标可见 且 其余28不可见） | PASS |
| C4 | 可见内容量下限（每项目 innerText>3000 且可见） | PASS |
| C5 | 截图留痕（overview/p0 @1440） | PASS |

### C 段明细

- C1 OK：静态集合=True（各 29）；运行时键解析不合格 0/29
- C2 OK：{'n': 1, 'id': 'view-overview', 'h': 2678, 'len': 3426, 'disp': 'block'}
- C3 OK：29 项中不合格 0 项
- C4 OK：28 项中 <3000 或不可见的 0 项
- C5 OK：截图 E:\不良ABS穿透研究\清算28单_单项目穿透\_校验件\_过程\shot_overview_1440.png / E:\不良ABS穿透研究\清算28单_单项目穿透\_校验件\_过程\_shot_p0_1440.png

### 真空通过机理（方法论结论，务必写入）

`pen_report_liq28.py:1144` 以 `views[v.id]`（键=`view-p0`）建表，而 `select()` 以侧栏 `data-view`（`p0`）查询 → **29/29 全部落空** → 所有 `.view` 全程 `display:none`（白屏）。此时原 B 段断言**全部真空通过**：
- **B4 空卡/超大空白**：面板 `display:none` 时 `offsetHeight=0`，「空卡」与「高度差>120px」**双双不可能命中** → 真空通过；
- **B3 溢出**：无内容渲染 ⇒ `scrollWidth-clientWidth=0` → 真空通过；
- **B2 段落存在性**：`querySelector` 可命中 `display:none` 元素 → 通过；
- **B1 id 唯一/集合对应**：仅比对两侧集合本身，未验证「以 data-view 能否查到面板」→ 通过；
- **B6 console error=0**：`views[view]` 为 `undefined` 有 `if` 守卫、不抛错 → 通过。

⇒ **教训：断言必须在「渲染可见」的前提下验证，不能只验证 DOM 存在。C 段即为此而设。**

### 变异测试（证明 C 段非真空：仅对**临时副本**重新注入 :1144 缺陷；不改真实产物）

- REAL 键表达式出现 1 次；变异副本已生成于 E:\不良ABS穿透研究\清算28单_单项目穿透\_校验件\_过程\_tmp_broken_report.html
- ---- 变异副本（注入 :1144 缺陷） ----
- C1 = False（static=True runtime_bad=29/29）
- C2 = {'n': 0}
- C3 = False（不合格 29 项，示例 [('overview', {'disp': 'none', 'h': 0, 'nvis': 0}), ('p0', {'disp': 'none', 'h': 0, 'nvis': 0}), ('p1', {'disp': 'none', 'h': 0, 'nvis': 0})]）
- C4 = False（不合格 28 项，示例 [('p0', {'len': 6812, 'h': 0}), ('p1', {'len': 6655, 'h': 0}), ('p2', {'len': 7797, 'h': 0}), ('p3', {'len': 7566, 'h': 0}), ('p4', {'len': 8368, 'h': 0})]）
- ---- 真实产物 ----
- C1 = True（static=True runtime_bad=0/29）
- C2 = {'n': 1, 'id': 'view-overview', 'h': 1683, 'len': 1934, 'disp': 'block'}
- C3 = True（不合格 0 项，示例 []）
- C4 = True（不合格 0 项，示例 []）

**结论**：C2/C3/C4 对缺陷敏感（变异副本上 FAIL）；**C1 原「静态集合相等」式不敏感**——缺陷是 JS 运行时键解析，DOM 两个集合恒等 ⇒ 已把 C1 **加强**为「静态集合相等 **且** 运行时键解析（点击每项后 `.view.on` 恰 1 且 id==view-{data-view}）」，加强后 C1 在变异副本上 FAIL。另：**C4 必须附 `offsetHeight>0` 可见性守卫**——`display:none` 元素的 `innerText` 实测返回 textContent（6812 字符 > 3000），不守卫将真空通过。真实产物上 C1–C5 全 PASS。

## D 段：图表裁切/缩放/隐藏内容（28 面板 × 四档宽度，逐 SVG 量测）

| 编号 | 断言 | gate | 结果 |
|---|---|---|---|
| D1 | 无裁切（svg.right <= 父内容右缘+1） | yes | PASS |
| D2 | 无缩放失真（|渲染宽/viewBox宽 - 1| <= 0.002） | yes | PASS |
| D3a | （仅记录）literal text.x <= 父内容宽 | no(记录) | PASS |
| D3b | 无隐藏内容（渲染 bbox 右缘 <= 父内容右缘+1） | yes | PASS |
| D4 | 覆盖率守卫（每面板 >=1 张 SVG；总数 > 0） | yes | PASS |
| D5 | 容器不掩盖溢出（父 overflow-x == visible） | yes | PASS |
| D6 | ★宽度扫描 900→1800 步长20（overview+28面板）D1/D2/D3b/D5 全过 | yes | PASS |
| D7 | ★动画终态==静态（播放完毕 vs reduced；几何≤0.5px/文本一致） | yes | PASS |
| D8 | ★reduced-motion 降级（常态有动画；reduce 下 animation-name 全 none） | yes | PASS |

## H 段：布局对标 v18（★本轮新增；全部 computed style / 几何实测）

| 编号 | 断言 | 结果 | 实测 |
|---|---|---|---|
| H1 | 内容区居中收窄（.view.on 1280 居中；逐档×29） | PASS | H1 OK：逐档 max-width 实测={1024: ['1280px'], 1280: ['1280px'], 1440: ['1280px'], 1680: ['1280px']}；offsetWidth[min,max]={1024: [1024, 1024], 1280: [1032, 1032], 1440: [1192, 1192], 1680: [1280, 1280]}；margin 左右相等={1024: True, 1280: True, 1440: True, 1680: True}；不合格 0 项 |
| H2 | 卡片阴影材质（.card 100% 有阴影；圆角≥12） | PASS | H2 OK：.card 阴影非 none 比例=100.0%(339/339)；border-radius min/max=12.0/12.0（≥12）；.fold 有阴影=False .chart 有阴影=True |
| H3 | KPI 整体条（column-gap=1px+父底色；.kpi .v=22px） | PASS | H3 OK：KPI 容器（含 .kpi 子）=112 个；column-gap=1px 且 背景非透明 的不合格=0；.kpi .v font-size=22.0px（22±0.5） |
| H4 | 表格去竖线+双向吸附（逐档） | PASS | H4 OK：逐档 (表数,separate,侧框非0,th粘顶/总,td1粘左/总)={1024: (168, 168, 0, 1632, 1632, 2045, 2045), 1280: (168, 168, 0, 1632, 1632, 2045, 2045), 1440: (168, 168, 0, 1632, 1632, 2045, 2045), 1680: (168, 168, 0, 1632, 1632, 2045, 2045)}；不合格 0 档 |
| H5 | 章节头渐变序号块（≥224；每面板≥8） | PASS | H5 OK：.sec-num 全页=224（≥224）；每项目面板最少=8（≥8）；含 gradient=224/224；白字=224/224；样例 bg=linear-gradient(150deg, rgb(59, 74, 102) 0%, rgb(26, 34, 48) 100%) color=rgb(255, 255, 255) |
| H6 | Hero 渐变顶线（::before 3px+gradient） | PASS | H6 OK：.hero 存在=True；::before height=3px bg=linear-gradient(150deg, rgb(59, 74, 102) 0%, rgb(26, 34, 48) 100%)；h1 font-size=21（≥20） |
| H7 | 折叠卡平滑展开+内容完整+交互 | PASS | H7 OK：.fold-b 总数=280（display=grid 280；transition 含 grid-template-rows 280，prop=grid-template-rows）；展开无裁切=5/5 [(0, 1440, 1440, 1440, 1440, 1134), (1, 1763, 1763, 1763, 1763, 1134), (2, 690, 690, 690, 690, 1134), (3, 2584, 2584, 2584, 2584, 1134), (4, 266, 266, 266, 266, 1062)]；收起高度≈0=5/5 [(0, 0, 1134 |
| H8 | 数字对齐（tabular-nums） | PASS | H8 OK：.kpi .v font-variant-numeric=tabular-nums；金额单元(num)=tabular-nums |
| H9 | 媒体查询分档（1100/900/640） | PASS | H9 OK：1100→KPI track=2（期望2）；900→.grid2 track=1（期望1）；640→KPI track=1（期望1）；不合格=0 |
| H10 | 画布渐层（linear-gradient+fixed） | PASS | H10 OK：body background-image=linear-gradient(rgb(234, 238, 244) 0%, rgb(232, 236, 243) 100%)；background-attachment=fixed；bg-color=rgb(234, 238, 244) |
| H11 | 数值零变化（5 单×3 项+全 28 扫） | PASS | H11 OK：抽检 5 单×3 项：①=5/5 ②=5/5 ③=5/5；全 28 单 data-attr 全扫：① ② 失配=0；不合格=0 [] |
| H12 | 可见文本无转义标签字面（源+innerText） | PASS | H12 OK：HTML 源『转义标签字面』=元素 0 个 / token 0 个（标签分布={}；`&quot;`=0；双重转义=0）；渲染可见文本字面 `<tag`=0（逐面板={}）；源样例=[] |
| H13 | KPI 容器无灰块+无空尾格 | PASS | H13 OK：面板数=28 ｜ 容器=112（非零几何=112）｜ (a) 不合格=0 ｜ (b) 不合格=0 ｜ 零几何=0；项数分布={8: 28, 23: 28, 3: 28, 4: 28}；附报 项数≥7（不按 b 判红；全底色==单元格色=True） |
| H14 | 最宽矩阵面板非真空溢出核对（四档） | PASS | H14 OK：最宽矩阵面板=p17（列=32；**前置已切该面板并展开全部折叠卡·非真空**）；逐档 (视口,pageOverflow,列,wrapClient,wrapScroll,容器内超出,overflowX,表右越界[允许])=[(1024, 0, 32, 910, 2477, 1567, 'auto', True), (1280, 0, 32, 902, 2675, 1773, 'auto', True), (1440, 0, 32, 1062, 2675, 1613, 'auto', True), (1680, 0, 32, 1150, 2675, 1525, 'auto', Tr |
| H15 | 节标题锚点守卫（去标签纯文本 8 节标题可定位） | PASS | H15 OK：逐面板去标签纯文本命中节标题；面板数=28；总命中=224（期望 28×8=224）；顺序①–⑧=True；不合格 0 |
| H16 | 检查器留痕守卫（sha256 == changelog 末条 after_sha256） | PASS | 本次 sha256=db059048da94826cf0fe61a4e0b84a3027c03df33ec193e9542ad7e4e0f3835c（mtime=2026-09-22 14:17:36）；changelog=_chk_changelog.md（留痕 8 条）；末条 after_sha256=db059048da94826cf0fe61a4e0b84a3027c03df33ec193e9542ad7e4e0f3835c；一致=True |
| H17 | 段完成性守卫（10 段 begin&end 且无 SKIP） | PASS | A[begin=True end=True pass=18 fail=0]；B[begin=True end=True pass=9 fail=0]；C[begin=True end=True pass=5 fail=0]；D[begin=True end=True pass=10 fail=0]；H[begin=True end=True pass=16 fail=0]；R[begin=True end=True pass=4 fail=0]；S[begin=True end=True pass=2 fail=0]；V[begin=True end=True pass=2 fail=0]；F[begin=True end=True pass=18 fail=0]；G[begin=True end=True pass=7 fail=0] |

### D6/D7/D8 明细

- D6：(46, [])
- D7：(125, 115, [])
- D8：(115, 0, [])

### D 段明细（逐宽度不合格数 / 比值 min-max / SVG 总数 / overflow-x 分布）

- **D1** OK：不合格 0 项（逐宽度 {1024: 0, 1280: 0, 1440: 0, 1680: 0}）
- **D2** OK：不合格 0 项；渲染/viewBox 比值 min/max=1.0/1.0
- **D3a** （仅记录·不 gate）literal(text.x) 不合格 0 项 —— 本族 `<text>` 无 `x` 属性（靠父 `<g>` transform 定位）⇒ 该测法对本报告族**永久真空**，仅作通用性保留，不得据其判绿。
- **D3b** OK（gate）：渲染 bbox 右缘 不合格 0 项（逐宽度 {1024: 0, 1280: 0, 1440: 0, 1680: 0}）
- **D4** OK：四档 SVG 总数={1024: 370, 1280: 370, 1440: 370, 1680: 370}；0 图(面板,宽)项 0 个
- **D5** OK（判据：overflow-x 必须=visible，hidden/auto 均 FAIL）：分布={'visible': 1480}；非 visible 的 0 项

**判据**：D1 `svg.getBoundingClientRect().right ≤ 父内容右缘+1`；D2 `|renderedWidth÷viewBoxWidth − 1| ≤ 0.002`；D3b `text.getBoundingClientRect().right ≤ 父内容右缘+1`；D5 父容器 computed `overflow-x` **必须为 `visible`**（裁定改严：`hidden` 与 `auto` 均 FAIL）。

### 三条「真空陷阱」（方法论，务必留存）

1. **高度类断言在 `display:none` 下恒不命中**：B4「空卡/高度差>120px」在白屏时元素 `offsetHeight=0`，两项双双不可能命中 → 假绿（C 段即为此而设）。
2. **`innerText` 在未渲染时回退 `textContent`**：`display:none` 元素 `innerText` 仍返回全文（实测 6812 字符）⇒ 裸 `innerText.length>3000`（C4）会假绿，必须附 `offsetHeight>0` 可见性守卫。
3. **`text.x` 在 transform 定位时恒为 0**：本报告族 SVG `<text>` **不带 `x` 属性**（靠父 `<g>` 的 `transform` 定位）⇒ `text.x`（D3a）**永久真空**；只有渲染 `bbox.right`（D3b）才敏感。

红/绿留档：**红**=`_过程\_chk_D_before_fix.txt`（对裁切版副本 `_过程\_tmp_clip_report.html`，免疫时序）；**绿**=`_过程\_chk_D_after_fix.txt`。

## 四档宽度横向溢出（px）

| 宽度 | max(scrollWidth-clientWidth) |
|---|---|
| 1024 | 0 |
| 1280 | 0 |
| 1440 | 0 |
| 1680 | 0 |

## 其它

- 文本裁切节点数：0
- 空卡片：0 / 超大空白(>120px)：None / 卡片总数：339
- console error 数：0
- B8 data-*：{'has': 28, 'compFalse': 0, 'both': 0, 'neither': 0, 'det': [], 'falseKeys': []}
- B9 非全精度属性：[]