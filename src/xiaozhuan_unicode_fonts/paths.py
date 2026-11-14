"""数据源定位与静态映射表加载（本仓库自包含，不依赖 zhuan）。

外部数据只有 U3D000.pdf（约 40MB，不入 git，放本仓库根目录），
下载地址见 PDF_URL。

静态映射表在 data/（由 zhuan/seal.db 经 tools/export_static_data.py
导出，提交进 git；再生成方法见 docs/agent.md「靜態映射數據」一节）：
  - seal_sources.tsv：seal_cp, mcjk_cp, thx, ccz, qjz, dyc
  - modern_map.tsv：code, seal_cp（通行字→小篆码位）
  - sw_pos.tsv：head, seal_cp（說文字头对位）
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[2]   # 仓库根（src/<pkg>/paths.py）
DATA = ROOT / "data"
BUILD = ROOT / "build_svg"                    # 中间产物：逐页 SVG＋paths json
DIST = ROOT / "dist"                          # 交付物：四款 OTF
PDF_URL = "https://www.unicode.org/Public/18.0.0/charts/PDF/U3D000.pdf"


def version() -> str:
    """字体版本号，唯一来源为 pyproject.toml。"""
    from importlib.metadata import version as v
    return v("xiaozhuan-unicode-fonts")


def find_pdf() -> Path:
    p = ROOT / "U3D000.pdf"
    if p.exists():
        return p
    raise SystemExit(
        f"缺 U3D000.pdf（约 40MB，不入 git）：请下载 {PDF_URL}\n"
        f"放到 {p}（或执行 just pdf）")


def load_tsv(name: str):
    with open(DATA / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_seal_sources():
    """返回 (fam_map, mcjk_of)：
    fam_map: {thx|ccz|qjz|dyc: {编号串: seal_cp}}（空值跳过）
    mcjk_of: {seal_cp: 隸定字字符}"""
    fam_map = {k: {} for k in ("thx", "ccz", "qjz", "dyc")}
    mcjk_of = {}
    for row in load_tsv("seal_sources.tsv"):
        cp = int(row["seal_cp"])
        for k in fam_map:
            if row[k]:
                fam_map[k][row[k]] = cp
        if row["mcjk_cp"]:
            mcjk_of[cp] = chr(int(row["mcjk_cp"]))
    return fam_map, mcjk_of


def load_modern_map():
    """通行字 → 小篆码位。"""
    return {int(r["code"]): int(r["seal_cp"]) for r in load_tsv("modern_map.tsv")}


def load_sw_pos():
    """說文字头对位表：{字: 碼位}（data/sw_pos.tsv）。"""
    out = {}
    for row in load_tsv("sw_pos.tsv"):
        out[row["head"]] = int(row["seal_cp"])
    return out
