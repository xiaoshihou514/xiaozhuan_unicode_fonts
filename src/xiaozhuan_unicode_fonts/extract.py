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

import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

from .paths import BUILD as OUTDIR, find_pdf, load_seal_sources
UPEM = 2048
PAGES = None                   # 全量；build_fonts_svg 打开 PDF 后按 doc.page_count 取

FAMS = ("thx", "ccz", "qjz", "dyc")

TOKEN_RE = re.compile(r"^(TH|C|K|D)-([XY]?\d{3,6})$")
FAM_OF_PREFIX = {"TH": "thx", "C": "ccz", "K": "qjz", "D": "dyc"}

PATH_CMD_RE = re.compile(r"([MmLlCcZzHhVv])\s*((?:-?[\d.]+(?:[, ]\s*-?[\d.]+)*)*)")


# ---------- 每頁處理 ----------

def page_svg(pno):
    out = OUTDIR / f"p{pno}.svg"
    if not out.exists():
        subprocess.run(["pdftocairo", "-svg", "-f", str(pno), "-l", str(pno),
                        str(find_pdf()), str(out)], check=True, capture_output=True)
    return out.read_text()


def parse_svg(svg):
    if "fill-rule" in svg and "evenodd" in svg:
        raise SystemExit("頁面 SVG 含 evenodd 填充規則，解析語義會變，請先確認 poppler 輸出")
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


def process_page(pno, fam_map):
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

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    fam_map, _ = load_seal_sources()

    global doc
    doc = pymupdf.open(find_pdf())
    pages = range(1, doc.page_count + 1)   # S1：页数取自 PDF，不写死
    if argv:
        if "-" in argv[0]:
            a, b = argv[0].split("-")
            pages = range(int(a), int(b) + 1)
        else:
            pages = [int(argv[0])]

    OUTDIR.mkdir(exist_ok=True)
    all_paths = defaultdict(dict)
    for pno in pages:
        got = process_page(pno, fam_map)
        for fam, m in got.items():
            all_paths[fam].update(m)

    out = {fam: {str(cp): d for cp, d in all_paths.get(fam, {}).items()} for fam in FAMS}

    # S5：提取完整性门禁——每款提取数必须等于映射表编号数
    ok = True
    for fam in FAMS:
        want = set(fam_map[fam].values())
        got = set(all_paths.get(fam, {}))
        missing = sorted(want - got)
        extra = sorted(got - want)
        print(f"{fam}: 应提 {len(want)}，实提 {len(got)}，缺 {len(missing)}，多 {len(extra)}",
              file=sys.stderr)
        if missing:
            ok = False
            preview = ", ".join(f"U+{c:X}" for c in missing[:20])
            print(f"  缺失码位示例: {preview}{' ...' if len(missing) > 20 else ''}",
                  file=sys.stderr)
        if extra:
            ok = False
            print(f"  多余码位: {[hex(c) for c in extra[:10]]}", file=sys.stderr)
    if not ok:
        sys.exit("提取完整性门禁未通过（Q2）：存在漏提/多提，拒绝产出 paths 数据")

    # M8：全量运行只写固定文件名，并清理其它 paths_*.json
    for old in OUTDIR.glob("paths_*.json"):
        old.unlink()
    (OUTDIR / "paths_all.json").write_text(json.dumps(out))
    for fam in FAMS:
        print(f"{fam}: {len(out[fam])} 字形 path", file=sys.stderr)


if __name__ == "__main__":
    main()
