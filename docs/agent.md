# 字体组工作文档（fonts 仓库）

面向维护者：字体管线架构、构建、发布与协作约定。面向使用者的下载与安装见[仓库 README](../README.md)。

## 一、管线架构

单一 SVG 管线（自包含，不依赖 zhuan 环境）：

```
U3D000.pdf（Unicode 18.0 码表，约 40MB，不入 git，放仓库根目录）
  │
  ├─ build_fonts_svg.py       pdftocairo 逐页 SVG（poppler 渲染正确性已被位图管线长期验证）
  │     pymupdf 读 Arial 标注（TH/C/K/D-xxxxx，有 ToUnicode）定位每格四家正形，
  │     编号经 data/seal_sources.tsv 反查码位 → paths json 缓存（build_svg/）
  │
  ├─ build_ttf_from_paths.py  建字＋度量归一＋交付
  │     Cu2Qu 转二次建 TTF 轮廓、T2CharString 原生三次建 CFF（同一变换）；
  │     归一以精确墨迹轮廓（BoundsPen）定位：墨迹高 96% em、宽封顶 98%、
  │     水平居中 0.5em、垂直 [−0.10, +0.86] em、全角步进；
  │     三层 cmap（小篆区／隸定字／通行字）→ 四款中文名 OTF（唯一交付物）
  │
  └─ check_centering.py       水平居中回归检测（偏差 >2% em 失败退出）
```

歷史沿革：早期 texttrace 管线（原 build_fonts.py＋fix_font_metrics.py）用
pymupdf texttrace 的 GID 几何配对，但 GID 与 PDF 渲染层字形编号语义不同且
非线性，曾致 cmap 指错字形（如「篆」→「匭」），已被 SVG 管线取代删除。

## 四、Release 发布流程

1. 本地构建＋`check_centering.py` 全过；
2. `git commit`（管线改动）；
3. `gh release create v{X.Y.Z}` ＋上传四款 OTF。**注意**：GitHub 会把
   非 ASCII 附件名清洗成 ASCII（gh 与 curl 直传 UTF-8 名均复现），故
   附件名用 PostScript 名（ASCII），中文以附件 label 展示，正文补对应关系；
4. 附件直传若失败（曾遇 HTTP 404），改「先建 Release 后逐个 upload」；
5. 同步把成品拷贝到 `../zhuan/`（宣发资产从 zhuan/ 读字体文件）。

当前版本：[v0.1.0](https://github.com/xiaoshihou514/xiaozhuan_unicode_fonts/releases/tag/v0.1.0)。

## 五、数据源与许可

- 字形：Unicode 18.0 码表 U3D000.pdf 参考字形，按
  [Unicode 授权条款](https://www.unicode.org/license.txt)使用，**仅供研究**，
  非规范出版字形；
- 码位标准：Unicode 18.0 Small Seal Script 区块（11,328 码位，
  SealSources.txt，Unicode UCD）；
- 查表链数据：Unihan_Variants.txt（Unihan）、維基文庫《說文解字》全文
  转录（zhuan/sw_download.py 抓取）；
- 脚本代码：[MIT](../LICENSE)。

## 六、已知坑（后来者必读）

1. **glyf 存储 bbox 含二次曲线控制点**（TrueType 规范行为），可远超视觉
   墨迹——任何"视觉居中/度量"一律以 BoundsPen 精确轮廓为准，勿信存储
   bbox（历史缺陷：陈昌治本曾因此 521 字形跑偏最大 26.2% em，2026-11 修复）；
2. texttrace GID 与 PDF 渲染层字形编号语义不同且非线性——不要用 GID
   互索引两个层面（SVG 管线存在的理由）；
3. GitHub 附件名清洗非 ASCII 字符；
4. `U3D000.pdf` 带版本号的 zipped 下载路径多已 404，用
   `Public/UCD/latest/ucd/` 路径；
5. zhuan 查表链构建须 `Unihan_Variants.txt` 在项目内且为真数据（404
   HTML 残骸会导致缺表，build_db.py 已改为报错——保持该约束）。

## 七、协作约定

- 本仓库（fonts）写作用域归字体组；`../zhuan`（查表链／seal.db）与
  `../langya`（输入法插件）改动分别归各自负责人，交叉改动先打招呼；
- 宣发资产从 `../zhuan/` 读字体与字形渲染文件，覆盖成品时保持
  zhuan/ 侧同名四款 OTF 同步更新（见第四节流程第 5 步）。
