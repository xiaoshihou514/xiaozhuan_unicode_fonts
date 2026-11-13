# xiaozhuan_unicode_fonts — 說文解字小篆四家字形复现管线

从 Unicode 18.0 官方码表 `U3D000.pdf` 提取《說文解字》小篆四家（陈昌治本 CCZ、
徐锴本 QJZ、段玉裁本 DYC、藤花树本 THX）字形轮廓，构建四款可安装字体，
三层 cmap：小篆区 U+3D000–3FC3F、說文隸定字、现代通行字。

**字形仅供研究使用**——来自 Unicode 码表参考字形，非规范出版字形。

## 下载成品

见 [Releases](../../releases)（首发版本将随字形居中修复一并发布）：四款
`说文小篆-{陈昌治,徐锴,段玉裁,藤花树}本.otf`。
仓库本身不含二进制（字体、PDF、数据库均不入 git）。

## 管线现状

| 脚本 | 状态 | 说明 |
|---|---|---|
| `legacy/build_fonts.py` + `legacy/fix_font_metrics.py` | 现行稳定交付管线 | pymupdf texttrace GID 几何配对，产出经度量归一（墨迹 96% em、全角步进） |
| `build_fonts_svg.py` + `build_ttf_from_paths.py` | 新一代 SVG 管线（重构中） | pdftocairo 矢量路径重建，绕开 texttrace GID 语义错配问题（如「篆」→「匭」），完成后接管交付 |

## 许可

- 脚本代码：[MIT](LICENSE)
- 字形数据条款：产出字体之字形源自 Unicode 18.0 码表（U3D000.pdf）参考字形，
  按 Unicode 授权条款使用，**仅供研究**，非规范出版字形。

## 构建前置条件

| 依赖 | 位置 | 获取方式 |
|---|---|---|
| `U3D000.pdf` | 本仓库根或项目根 | Unicode 18.0 码表（约 40MB，不入 git） |
| `seal.db` | 旁边 `../zhuan/seal.db` | 在 [zhuan](../zhuan) 项目运行 `uv run python build_db.py`（fonts 构建复用其查表链与数据库） |
| Python 依赖 | — | `pymupdf`、`fonttools`（poppler-utils 提供 `pdftocairo`，SVG 管线用） |

依赖处理：本仓库默认**与 zhuan 项目并排同树**（`../zhuan`），脚本经
`fontpaths.py` 自动定位数据源；zhuan 缺席时 SVG 管线自动降级为两层 cmap
（无通行字层）并给出警告。

## 构建

```bash
# SVG 管线（推荐，约数分钟；paths json 缓存后增量秒级）
pdftocairo -svg ...        # 由 build_fonts_svg.py 内部调用
python build_fonts_svg.py
python build_ttf_from_paths.py

# 现行 texttrace 管线（texttrace 扫描约 5 分钟，有缓存）
python legacy/build_fonts.py
python legacy/fix_font_metrics.py
```

## 数据源与许可

- 字形：Unicode 18.0 码表参考字形（Unicode 数据库以 [Unicode License](https://www.unicode.org/license.txt) 授权）
- 码位标准：Unicode 18.0 Small Seal Script 区块 U+3D000–3FC3F（11,328 码位）
- 查表链：《說文解字》对位数据来自 [zhuan 项目](../zhuan)（SealSources.txt、Unihan、維基文庫《說文解字》全文转录）
