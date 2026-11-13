"""数据源定位与静态映射表加载（本仓库自包含，不依赖 zhuan）。

外部数据只有 U3D000.pdf（约 40MB，不入 git，放本仓库根目录）：
  https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip 之外，
  码表 PDF 从 Unicode 18.0 发布页获取（见 README「构建前置条件」）。

静态映射表在 data/（由 zhuan/seal.db 一次性导出，提交进 git）：
  - seal_sources.tsv：seal_cp, mcjk_cp, thx, ccz, qjz, dyc
    （码表 PDF 内 TH/C/K/D 编号反查码位；隸定字码位供第二层 cmap）
    再生成方法：见 docs/agent.md「静态映射数据」一节。
  - modern_map.tsv：code, seal_cp（通行字→小篆码位，查表链产物）
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent


def find_pdf() -> Path:
    p = ROOT / "U3D000.pdf"
    if p.exists():
        return p
    raise SystemExit(
        "缺 U3D000.pdf（约 40MB，不入 git）：请从 Unicode 18.0 码表发布页下载，"
        f"放到 {ROOT}/U3D000.pdf（获取方式见 README）")


def load_tsv(name: str):
    with open(ROOT / "data" / name, encoding="utf-8", newline="") as f:
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
