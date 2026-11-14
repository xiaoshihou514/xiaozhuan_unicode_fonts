# 字体组工作文档（fonts 仓库）

面向维护者：字体管线架构、构建、发布与协作约定。面向使用者的下载与安装见[仓库 README](../README.md)。

## 一、管线架构

单一 SVG 管线（自包含，不依赖 zhuan 环境）。标准 uv 项目，代码在
`src/xiaozhuan_unicode_fonts/`，入口 `xiaozhuan-fonts`（cli.py），版本号唯一来源
为 `pyproject.toml`：

```
U3D000.pdf（Unicode 18.0 码表，约 40MB，不入 git，放仓库根目录）
  │
  ├─ extract.py   pdftocairo 逐页 SVG（poppler 渲染正确性已被位图管线长期验证）
  │     pymupdf 读 Arial 标注（TH/C/K/D-xxxxx，有 ToUnicode）定位每格四家正形，
  │     编号经 data/seal_sources.tsv 反查码位 → paths json 缓存（build_svg/）
  │
  ├─ build.py     建字＋度量归一＋交付
  │     Cu2Qu 转二次建 TTF 轮廓、T2CharString 原生三次建 CFF（同一变换）；
  │     归一以精确墨迹轮廓（BoundsPen）定位：墨迹高 96% em、宽封顶 98%、
  │     水平居中 0.5em、垂直 [−0.10, +0.86] em、全角步进；
  │     三层 cmap（小篆区／隸定字／通行字）→ dist/ 四款中文名 OTF（唯一交付物）
  │
  └─ check.py     独立交付门禁 Q1–Q9（居中/映射/几何/度量，任一失败非零退出）
```

歷史沿革：早期 texttrace 管线（原 build_fonts.py＋fix_font_metrics.py）用
pymupdf texttrace 的 GID 几何配对，但 GID 与 PDF 渲染层字形编号语义不同且
非线性，曾致 cmap 指错字形（如「篆」→「匭」），已被 SVG 管线取代删除。

## 二、构建前置条件与命令

| 依赖 | 位置 | 说明 |
|---|---|---|
| uv | 命令行 | https://docs.astral.sh/uv/ |
| just（可选） | 命令行 | https://github.com/casey/just#packages |
| `U3D000.pdf` | 本仓库根目录 | [Unicode 18.0 码表](https://www.unicode.org/Public/18.0.0/charts/PDF/U3D000.pdf)（约 40MB，不入 git，`just pdf` 自动下载） |
| poppler-utils | 系统 | 提供 pdftocairo |

```bash
just otf                       # 下载 PDF（如缺）→ 提取 → dist/ 四款 OTF → 门禁
just check                     # 仅跑门禁
just release                   # 门禁＋工作区清洁检查＋dist/sha256sums.txt
uv run xiaozhuan-fonts         # 不用 just：全流程（extract/build/check 可单跑）
uv run xiaozhuan-fonts extract 190   # 调试：只提取第 190 页
```

## 三、靜態映射數據（data/）

| 文件 | 內容 | 維護方式 |
|---|---|---|
| `seal_sources.tsv` | seal_cp, mcjk_cp, TH/C/K/D 編號 | 導出腳本 |
| `modern_map.tsv` | code, seal_cp（通行字→小篆碼位） | 導出腳本 |
| `sw_pos.tsv` | head, seal_cp（說文字頭對位） | 導出腳本 |
| `隸定重码清单.tsv` | 94 個重碼字（「裁定」列待人工確認） | 手工 |
| `黄金映射.tsv` | 常用字→應得碼位（門禁 Q4 回歸基線） | 手工維護 |
| `分款回退.tsv` | 分款借形（dyc「上」→U+3D006，段注篆作「丄」） | 手工維護 |
| `分款缺口.tsv` | 官方數據缺口豁免（dyc 無「下」） | 手工維護 |
| `映射白名单.tsv` | 通行字映射顯式豁免（舌→U+3D660） | 手工維護 |

再生成（需 zhuan 環境）：

```bash
cd ../zhuan && .venv/bin/python ../fonts/tools/export_static_data.py
```

查表鏈修復說明（G1 根因）：zhuan 查表鏈優先級已改為「人工校訂別名 →
隸定本字（重碼時字頭碼位優先）→ 說文字頭對位 → 變體鏈（已剔除
`sw_gw` 古文從屬邊）→ OpenCC → 借聲符」。

## 五、Release 发布流程

1. `pyproject.toml` 改版本号，`just otf` 全过；
2. `git commit`（管线改动）；
3. `gh release create v{X.Y.Z}` ＋上传四款 OTF。**注意**：GitHub 会把
   非 ASCII 附件名清洗成 ASCII（gh 与 curl 直传 UTF-8 名均复现），故
   附件名用 PostScript 名（ASCII），中文以附件 label 展示，正文补对应关系；
4. 附件直传若失败（曾遇 HTTP 404），改「先建 Release 后逐个 upload」；
5. 同步把 `dist/` 成品拷贝到 `../zhuan/`（宣发资产从 zhuan/ 读字体文件）。

当前版本：[0.1.4](https://github.com/xiaoshihou514/xiaozhuan_unicode_fonts/releases/latest)。

## 六、数据源与许可

- 字形：Unicode 18.0 码表 U3D000.pdf 参考字形，按
  [Unicode 授权条款](https://www.unicode.org/license.txt)使用，**仅供研究**，
  非规范出版字形；
- 码位标准：Unicode 18.0 Small Seal Script 区块（11,328 码位，
  SealSources.txt，Unicode UCD）；
- 查表链数据：Unihan_Variants.txt（Unihan）、維基文庫《說文解字》全文
  转录（zhuan/sw_download.py 抓取）；
- 脚本代码：[MIT](../LICENSE)。

## 七、已知坑（后来者必读）

1. **glyf 存储 bbox 含二次曲线控制点**（TrueType 规范行为），可远超视觉
   墨迹——视觉居中/度量一律以 BoundsPen 精确轮廓为准（task-17 陈昌治本
   521 字形跑偏最大 26.2% em 的根因）；
2. **R1 起不回读已构建字形**：glyf 对象经 glyphSet 读取存在数据错位
   陷阱（task-17 时代 233 字形偏移的诱因）；
3. **pathops 输入必须取整**：浮点自交路径直接 simplify 会触发 skia
   丢区域缺陷（0x3FBB3/0x3DB8F 上半部丢失，v0.1.2 落地时实证）；
   pathops 输出为单段二次曲线，经 Qu2CuPen(all_cubic=True) 转三次；
4. texttrace GID 与 PDF 渲染层字形编号语义不同且非线性——不要用 GID
   互索引两个层面（SVG 管线存在的理由）；
5. GitHub 附件名清洗非 ASCII 字符；
6. `U3D000.pdf` 带版本号的 zipped 下载路径多已 404，用
   `Public/UCD/latest/ucd/` 路径；
7. zhuan 查表链构建须 `Unihan_Variants.txt` 在项目内且为真数据（404
   HTML 残骸会导致缺表，build_db.py 已改为报错——保持该约束）。

## 八、协作约定

- 本仓库（fonts）写作用域归字体组；`../zhuan`（查表链／seal.db）与
  `../langya`（输入法插件）改动分别归各自负责人，交叉改动先打招呼；
- 宣发资产从 `../zhuan/` 读字体与字形渲染文件，覆盖成品时保持
  zhuan/ 侧同名四款 OTF 同步更新（见第四节流程第 5 步）。
