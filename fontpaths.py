"""数据源定位：U3D000.pdf 与 seal.db 在本仓库或旁边的 zhuan/ 中查找。

fonts 仓库只收管线源码，二进制与数据库不入 git：
  - U3D000.pdf：优先 fonts/U3D000.pdf，回退 ../U3D000.pdf；
    缺失时给出官方下载地址。
  - seal.db（zhuan 查表链产物）：优先 fonts/seal.db（手工拷贝），
    回退 ../zhuan/seal.db；缺失时提示先在 zhuan/ 构建。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PDF_URL = "https://www.unicode.org/Public/18.0.0/ucd/UCD.zip"  # 码表 PDF 另行下载


def find_pdf() -> Path:
    for p in (ROOT / "U3D000.pdf", ROOT.parent / "U3D000.pdf"):
        if p.exists():
            return p
    raise SystemExit(
        "缺 U3D000.pdf（约 40MB，不入 git）：请从 Unicode 18.0.0 码表发布页下载，"
        f"放到 {ROOT}/U3D000.pdf 或项目根目录")


def find_seal_db() -> Path:
    for p in (ROOT / "seal.db", ROOT.parent / "zhuan" / "seal.db"):
        if p.exists():
            return p
    raise SystemExit(
        "缺 seal.db（zhuan 查表链产物，不入 git）：请先在旁边 zhuan/ 目录运行"
        " uv run python build_db.py，或把 seal.db 拷到本仓库根目录")
