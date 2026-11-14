# Unicode 18小篆字体（說文解字）

从 Unicode 18.0 官方码表提取的《說文解字》小篆字体（陈昌治本、
徐锴本、段玉裁本、藤花树本）

**字形仅供研究使用**（Unicode协议），非规范出版字形。

[下载](../../releases)

## 构建

[MIT](LICENSE)。需 [uv](https://docs.astral.sh/uv/)、[just](https://github.com/casey/just)、poppler-utils（`pdftocairo`）。

```bash
just otf
```

会自动下载码表 [U3D000.pdf](https://www.unicode.org/Public/18.0.0/charts/PDF/U3D000.pdf)（约 40MB）， `dist/`为最终产物。不用 just 时，手动下载 PDF 后运行：

```bash
uv run xiaozhuan-fonts
```
