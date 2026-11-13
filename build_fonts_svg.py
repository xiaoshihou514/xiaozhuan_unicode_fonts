#!/usr/bin/env python3
"""從碼表 PDF 經 pdftocairo SVG 管線重建四款說文小篆字體。

舊 build_fonts.py 用 pymupdf texttrace 的 gid 直接索引 extract_font 的
glyf，但兩者的字形編號語義並不對應（同一視覺字形在 pdf 渲染層與嵌入
字體檔中 gid 不同且非線性），導致 cmap 指向錯字形（如「篆」→「匭」）。

本腳本徹底繞開 gid：
  1. pdftocairo -svg 把每頁字形轉成矢量 path（poppler 渲染正確性已被
     glyph.py 的位圖管線長期驗證）；
  2. pymupdf texttrace 只用來讀 Arial 標注文字（TH/C/K/D-xxxxx，有
     ToUnicode，可靠），拿到每格四家標注的位置；
  3. 標注正上方（x 對齊、基線在標注 top 上方 ~5.3pt）的 use 即該家
     正形字形的矢量 path；
  4. 編號經 seal.db 反查碼位，path 經 Cu2QuPen 轉 TrueType 二次曲線
     建字，cmap 三層（小篆區/隸定字/通行字）復用原邏輯。
"""
import io
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).parent
from fontpaths import find_pdf, find_seal_db   # noqa: E402
PDF = find_pdf()
DB = find_seal_db()
OUTDIR = ROOT / "build_svg"
UPEM = 2048
PAGES = range(1, 190)          # 1 基：碼表頁

FAMS = ("thx", "ccz", "qjz", "dyc")

TOKEN_RE = re.compile(r"^(TH|C|K|D)-(\d{4,6})$")
FAM_OF_PREFIX = {"TH": "thx", "C": "ccz", "K": "qjz", "D": "dyc"}

PATH_CMD_RE = re.compile(r"([MmLlCcZzHhVv])\s*((?:-?[\d.]+(?:[, ]\s*-?[\d.]+)*)*)")


# ---------- SVG path → 輪廓點 ----------

def svg_path_to_segments(d):
    """把 pdftocairo 的 path d 解析為 (命令, 絕對坐標點列) 序列。"""
    segs = []
    for cmd, argstr in PATH_CMD_RE.findall(d):
        vals = [float(v) for v in re.findall(r"-?[\d.]+", argstr)]
        segs.append((cmd, vals))
    return segs


class SvgPen:
    """把 SVG path（y 向下、基線 y=0）畫到 fontTools pen（y 向上）。"""

    def __init__(self, out_pen, scale):
        self.pen = out_pen
        self.s = scale

    def _pt(self, x, y):
        return (x * self.s, -y * self.s)

    def draw(self, d):
        pen = self.pen
        segs = svg_path_to_segments(d)
        cur = None
        start = None
        for cmd, v in segs:
            c = cmd.upper()
            if c == "M":
                if cur is not None:
                    pen.closePath()
                cur = self._pt(v[0], v[1])
                start = cur
                pen.moveTo(cur)
                rest = v[2:]
                for i in range(0, len(rest), 2):
                    cur = self._pt(rest[i], rest[i + 1])
                    pen.lineTo(cur)
            elif c == "L":
                for i in range(0, len(v), 2):
                    cur = self._pt(v[i], v[i + 1])
                    pen.lineTo(cur)
            elif c == "C":
                for i in range(0, len(v), 6):
                    p1 = self._pt(v[i], v[i + 1])
                    p2 = self._pt(v[i + 2], v[i + 3])
                    p3 = self._pt(v[i + 4], v[i + 5])
                    pen.curveTo(p1, p2, p3)
                    cur = p3
            elif c == "H":
                for x in v:
                    cur = self._pt(x, cur[1] / self.s if cur else 0)
                    pen.lineTo(cur)
            elif c == "V":
                for y in v:
                    cur = self._pt(cur[0] / self.s if cur else 0, y)
                    pen.lineTo(cur)
            elif c == "Z":
                if cur is not None:
                    pen.closePath()
                    cur = start
        if cur is not None:
            pen.closePath()


def path_bbox(d):
    xs, ys = [], []
    for cmd, v in svg_path_to_segments(d):
        c = cmd.upper()
        if c in ("M", "L"):
            xs += v[0::2]; ys += v[1::2]
        elif c == "C":
            xs += v[0::2]; ys += v[1::2]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


# ---------- 每頁處理 ----------

def page_svg(pno):
    out = OUTDIR / f"p{pno}.svg"
    if not out.exists():
        subprocess.run(["pdftocairo", "-svg", "-f", str(pno), "-l", str(pno),
                        str(PDF), str(out)], check=True, capture_output=True)
    return out.read_text()


def parse_svg(svg):
    defs = dict(re.findall(r'<g id="(glyph-[\d-]+)">\s*<path d="([^"]+)"/>', svg))
    uses = [(m[0], float(m[1]), float(m[2]))
            for m in re.findall(r'<use xlink:href="#(glyph-[\d-]+)" x="([\d.]+)" y="([\d.]+)"/>', svg)]
    return defs, uses


def source_labels(page):
    """讀四家來源編號標注：[(文字, x0, x1, y_top)]。"""
    out = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        if TOKEN_RE.match(text):
            out.append((text, x0, x1, y0))
    return out


def process_page(pno, fam_map, con, sink):
    """處理一頁：返回 {family: {seal_cp: path_d}}。"""
    page = doc[pno - 1]
    tokens = source_labels(page)
    if not tokens:
        return {}
    svg = page_svg(pno)
    defs, uses = parse_svg(svg)

    # use 按基線 y 分桶，便於按 (x, y) 查找
    by_line = defaultdict(list)
    for ref, x, y in uses:
        by_line[round(y, 1)].append((x, ref))

    got = defaultdict(dict)
    stats = defaultdict(lambda: [0, 0])
    for text, x0, x1, ytop in tokens:
        m = TOKEN_RE.match(text)
        prefix, num = m.groups()
        fam = FAM_OF_PREFIX[prefix]
        key = f"{prefix}-{num}"
        cp = fam_map[fam].get(key)
        if cp is None:
            continue
        # 字形：基線 = 標注 top - 5.3；x 與標注左緣對齊（±3pt）
        base_y = round(ytop - 5.3, 1)
        cands = [(x, ref) for x, ref in by_line.get(base_y, []) if abs(x - x0) < 3.5]
        stats[fam][0] += 1
        if len(cands) != 1:
            if not cands:
                # 基線取整可能漂移，放寬重找
                for dy in (-0.1, 0.1, -0.2, 0.2):
                    cands = [(x, ref) for x, ref in by_line.get(round(base_y + dy, 1), [])
                             if abs(x - x0) < 3.5]
                    if len(cands) == 1:
                        break
        if len(cands) == 1:
            _, ref = cands[0]
            d = defs.get(ref)
            if d:
                got[fam][cp] = d
                stats[fam][1] += 1
    for fam in FAMS:
        n_t, n_g = stats[fam]
        if n_t:
            print(f"  頁{pno} {fam}: 標注 {n_t} 命中 {n_g}", file=sys.stderr)
    return got


# ---------- 主流程 ----------

def main():
    pages = PAGES
    if len(sys.argv) > 1:
        if "-" in sys.argv[1]:
            a, b = sys.argv[1].split("-")
            pages = range(int(a), int(b) + 1)
        else:
            pages = [int(sys.argv[1])]

    con = sqlite3.connect(DB)
    # 編號 → 碼位（每家）
    fam_map = {}
    for fam in FAMS:
        rows = con.execute(f"SELECT {fam}, seal_cp FROM seal_char WHERE {fam} IS NOT NULL")
        fam_map[fam] = dict(rows)

    global doc
    doc = pymupdf.open(PDF)

    OUTDIR.mkdir(exist_ok=True)
    all_paths = defaultdict(dict)
    for pno in pages:
        got = process_page(pno, fam_map, con, None)
        for fam, m in got.items():
            all_paths[fam].update(m)
        (OUTDIR / f"paths_p{pno if isinstance(pno, int) else pno}.json").unlink(missing_ok=True)

    out = {fam: {str(cp): d for cp, d in all_paths.get(fam, {}).items()} for fam in FAMS}
    tag = f"{pages[0]}-{pages[-1]}" if len(pages) > 1 else str(pages[0])
    (OUTDIR / f"paths_{tag}.json").write_text(json.dumps(out))
    for fam in FAMS:
        print(f"{fam}: {len(out[fam])} 字形 path", file=sys.stderr)


if __name__ == "__main__":
    main()
