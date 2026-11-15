# tests

本包 1.0 不再附带旧工作台测试脚本（旧脚本硬编码 `E:\...`，换机必坏）。

交互门禁统一走：

```bash
python -X utf8 scripts/gate.py --html dist/不良ABS多行工作台_策略与投资人回报_尊享版_V9.html
```

它覆盖：13 ECharts、现金流 74/8、6 双列、KPI 74→54→74、Ctrl 多选、现金流行→银行页、银行页/表格、0 JS 错误。

需要扩展时，在 `scripts/verify_workbench.py` 里加断言，不要在测试里写死盘符。
