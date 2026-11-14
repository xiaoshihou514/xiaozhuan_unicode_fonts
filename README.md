# Unicode 18小篆字体（說文解字）

<img width="1200" height="507" alt="古诗诗牌-四家对照预览" src="https://github.com/user-attachments/assets/62c3b2bd-2796-479e-ae86-80f544ca087b" />
<img width="1200" height="474" alt="现代句子-天安门预览" src="https://github.com/user-attachments/assets/e3e9ab30-ba8b-46cf-a391-6a9040d3abf5" />
<img width="1200" height="580" alt="现代句子-山川异域预览" src="https://github.com/user-attachments/assets/80c8ab04-09aa-42db-8ebf-e80aa36b5015" />
<img width="1200" height="664" alt="现代句子-艺术字预览" src="https://github.com/user-attachments/assets/493562e8-7ee3-40f6-b267-d8b5fdbc6ccb" />

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
