# Unicode 18小篆字体（說文解字）

从 Unicode 18.0 官方码表提取的《說文解字》小篆字体（陈昌治本、
徐锴本、段玉裁本、藤花树本）

**字形仅供研究使用**（Unicode协议），非规范出版字形。

[下载](../../releases)

## 构建脚本

[MIT](LICENSE)

| 依赖 | 位置 | 获取方式 |
|---|---|---|
| `U3D000.pdf` | 本仓库根或项目根 | Unicode 18.0 码表（约 40MB，不入 git） |
| Python 依赖 | — | `pymupdf`、`fonttools`（poppler-utils 提供 `pdftocairo`，SVG 管线用） |


```bash
pdftocairo -svg ...
python build_fonts_svg.py
python build_ttf_from_paths.py
```
