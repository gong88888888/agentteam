# Reviews

产品文档深析 / 版本升级参考方案。

| 目录 | 来源 | 结果 |
|---|---|---|
| `test1-product/` | `projects/test1/docs/product/product-baseline.md` | 11/11 角色门禁 pass，22/22 来源章节覆盖，含补丁/小版本/大版本预演与回滚方案 |

运行新的评审：

```bash
python start_product_review.py --doc <产品文档.md> --out reviews/<version> --real --kb
```

输出 `REFERENCE-PLAN.md`、`state/gates.json`、`docs/product-review/*.md`。
