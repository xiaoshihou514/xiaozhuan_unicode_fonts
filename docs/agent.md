# 字体组工作文档（fonts 仓库）

面向维护者：字体管线架构、构建、发布与协作约定。面向使用者的下载与安装见[仓库 README](../README.md)。

## 一、管线架构

数据流（现行稳定交付管线）：

```
U3D000.pdf（Unicode 18.0 码表，40MB，不入 git）
  │
  ├─ legacy/build_fonts.py          texttrace 扫描（约 5 分钟，缓存于 fonts_ext/trace.json）
  │    pymupdf texttrace 取每字形（字体×GID×坐标），
  │    与码位格四列锚点几何配对 → 码位→GID
  │    三层 cmap（小篆区／隸定字／通行字）→ shuowen-seal-{CCZ,QJZ,DYC,THX}.ttf
  │
  ├─ legacy/fix_font_metrics.py     度量归一＋转交付
  │    精确墨迹轮廓（BoundsPen，勿用含控制点的存储 bbox——见「已知坑」）
  │    墨迹高 96% em、宽封顶 98%、水平居中 0.5em、垂直 [−0.10, +0.86] em、
  │    全角步进；cu2qu 转 CFF → {说文小篆-陈昌治本,…}.otf（中文名，中间 TTF 删）
  │
  └─ build_fonts_svg.py ＋ build_ttf_from_paths.py    新一代 SVG 管线（重构中）
       pdftocairo 逐页 SVG → Arial 标注定位于正形 path（绕开 texttrace
       GID 语义错配问题，如「篆」→「匭」）→ paths json 缓存 → TTF/OTF
       质量达标后接管交付
```

字形视觉居中由 `fix_font_metrics.py` 保证，回归把关用 `check_centering.py`
（偏差 >2% em 即失败退出，可挂构建流水线）。

## 二、构建前置条件与命令

| 依赖 | 位置 | 说明 |
|---|---|---|
| Python ≥3.10 ＋ pymupdf、fontTools | 旁边 `../zhuan/.venv` 可复用 | 亦可用 uv 独立建环境 |
| `U3D000.pdf` | 本仓库根或项目根 | Unicode 官方码表，不入 git |
| `seal.db` | 旁边 `../zhuan/seal.db` | zhuan 查表链产物；`fontpaths.py` 自动定位 |
| poppler-utils（SVG 管线） | 系统 | 提供 pdftocairo |

```bash
# 现行管线
../zhuan/.venv/bin/python legacy/build_fonts.py        # texttrace 约 5 分钟（有缓存）
../zhuan/.venv/bin/python legacy/fix_font_metrics.py   # 归一＋CFF → 四款中文名 OTF
../zhuan/.venv/bin/python check_centering.py           # 居中回归检测（必须全过）

# 新一代 SVG 管线
../zhuan/.venv/bin/python build_fonts_svg.py           # 首次约 5 分钟（paths json 缓存后秒级增量）
../zhuan/.venv/bin/python build_ttf_from_paths.py      # → shuowen-seal-*.ttf/otf（英文名，未接管交付）
```

与 zhuan 的依赖关系：通行字 cmap 层跑 zhuan 完整查表链
（别名→本字→变体图→說文对位→OpenCC→借声符）；zhuan 缺席时 SVG 管线
降级为两层 cmap 并警告，legacy 管线则不可运行。两仓库须并排同树。

## 三、四款字体与三层 cmap

| 文件（PostScript 名） | 家族 | 碼表列 | 档位 |
|---|---|---|---|
| ShuowenSeal-ChenChangzhi（说文小篆-陈昌治本） | CCZ | C | 一形 |
| ShuowenSeal-XuKai（说文小篆-徐锴本） | QJZ | K | 二形 |
| ShuowenSeal-DuanYucai（说文小篆-段玉裁本） | DYC | D | 三形 |
| ShuowenSeal-TengHuaShu（说文小篆-藤花树本） | THX | TH | 四形 |

三层 cmap（format 12，优先级即序）：
1. 小篆区 U+3D000–3FC3F（11,328 码位，Unicode 18.0 权威标准）；
2. 說文隸定字码位（seal_char 的 kSEAL_MCJK 反查）；
3. 通行字（跑完整查表链，覆盖≈转换器）。

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
