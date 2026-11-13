#!/usr/bin/env python3
"""诊断 build_fonts_svg.py 漏提：对 seal_sources.tsv 中有编号、但 paths json 未提取到的
码位，按「是否在 PAGES 范围内」「编号是否被 TOKEN_RE 接受」归类，并验证若修正这两处，
现有「标注正上方 5.3pt、横向 ±3.5pt」定位规则能否唯一命中字形（即可回收）。

只读：缺失页的 SVG 生成到临时目录，不写 build_svg/。
用法（fonts/ 下）：UV_CACHE_DIR=$PWD/.uv-cache uv run --offline python audit/工具/漏提诊断.py
"""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pymupdf

FONTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FONTS))
import build_fonts_svg as B                     # noqa: E402
from fontpaths import load_seal_sources        # noqa: E402

RELAXED = re.compile(r"^(TH|C|K|D)-([XY]?\d{3,6})$")

paths = json.loads((FONTS / "build_svg" / "paths_1-189.json").read_text())
fam_map, _ = load_seal_sources()
doc = pymupdf.open(B.PDF)
print(f"PDF 页数 {doc.page_count}；build_fonts_svg.PAGES = {B.PAGES}")
tmp = Path(tempfile.mkdtemp())
total, recover = Counter(), Counter()
detail = []
for pno in range(1, doc.page_count + 1):
    toks = [(w[4], w[0], w[1]) for w in doc[pno - 1].get_text("words") if RELAXED.match(w[4])]
    need = []
    for text, x0, ytop in toks:
        fam = B.FAM_OF_PREFIX[RELAXED.match(text).group(1)]
        cp = fam_map[fam].get(text)
        if cp is not None and str(cp) not in paths[fam]:
            need.append((text, x0, ytop, fam, cp))
    if not need:
        continue
    svg = FONTS / "build_svg" / f"p{pno}.svg"
    if not svg.exists():
        svg = tmp / f"p{pno}.svg"
        subprocess.run(["pdftocairo", "-svg", "-f", str(pno), "-l", str(pno), str(B.PDF), str(svg)],
                       check=True, capture_output=True)
    defs, uses = B.parse_svg(svg.read_text())
    for text, x0, ytop, fam, cp in need:
        why = []
        if pno not in B.PAGES:
            why.append(f"第{pno}页不在 PAGES")
        if not B.TOKEN_RE.match(text):
            why.append("编号被 TOKEN_RE 拒收（X/Y 系列）")
        why = "＋".join(why) or "其他"
        base = round(ytop - 5.3, 1)
        c = [r for r, x, y in uses if abs(x - x0) < 3.5 and abs(round(y, 1) - base) <= 0.21]
        ok = len(c) == 1 and c[0] in defs
        total[(fam, why)] += 1
        recover[(fam, why)] += ok
        detail.append(f"{fam}\t{text}\tU+{cp:X}\t第{pno}页\t{why}\t{'可唯一回收' if ok else '需人工'}")
for k in sorted(total):
    print(f"  {k[0]} {k[1]}: {total[k]}（按现规则可唯一回收 {recover[k]}）")
out = FONTS / "audit" / "数据" / "漏提诊断.tsv"
out.write_text("款\t编号\t码位\t页\t原因\t回收性\n" + "\n".join(detail) + "\n", encoding="utf-8")
print(f"合计 {sum(total.values())}，可回收 {sum(recover.values())} → {out.relative_to(FONTS)}")
