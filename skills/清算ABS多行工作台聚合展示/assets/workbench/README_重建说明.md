# V9 基线与重建说明

`不良ABS多行工作台_策略与投资人回报_尊享版_V9.html` 在本包里有两个身份：

1. **参考产物**：用户已验收的 V9；
2. **重建基线**：注入器会先剥离旧的 `V3_STYLE/LIB/DATA/APP` 四块，再按当前 `assets/source` + `assets/data/_rows_all.json` 重注。

因此：

- 不要把 V9 当“只读产物”直接手改；改源码后重建；
- 不要删掉 `<!--V3_*_START/END-->` 标记；没有标记就无法幂等替换；
- 重建必须字节一致：11,385,763 B / `8ae21fd0…`；
- 换新数据集时，基础壳的 `META` / `REPORTS` / `SLICE_ROWS` 也要一起换（见 references/00 第 6 节）；
- V9 的 off-canvas drawer 在 390px 会增加 `document.scrollWidth`，这是基础壳行为，不作为 G3 失败条件。

构建：

```bash
python -X utf8 scripts/build_workbench.py --check
```
