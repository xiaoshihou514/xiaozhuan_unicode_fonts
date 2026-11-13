#!/usr/bin/env python3
"""码表 PDF 原形 vs 交付 OTF 字形 并排对照图（只读，输出到 audit/证据/）。

用法：uv run --offline python audit/工具/对照图.py 输出名.png 家:码位 [家:码位 ...]
  家 ∈ ccz qjz dyc thx；码位如 3E526。
每行：左＝PDF 该格高分辨率光栅（pymupdf 800dpi 裁切，即码表真值），
      中＝交付 OTF（Release v0.1.1）同字 FreeType 光栅，
      右＝两者孔洞标注（红＝OTF 封闭白区）。
"""
import re
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FONTS))
from fontpaths import load_seal_sources   # noqa: E402

REL = {"ccz": "ShuowenSeal-ChenChangzhi.otf", "qjz": "ShuowenSeal-XuKai.otf",
       "dyc": "ShuowenSeal-DuanYucai.otf", "thx": "ShuowenSeal-TengHuaShu.otf"}
PRE = {"ccz": "C", "qjz": "K", "dyc": "D", "thx": "TH"}
S = 360
LAB = "/home/xiaoshihou/.local/share/fonts/lxgw-wenkai-v1.522/LXGWWenKai-Medium.ttf"

fam_map, _ = load_seal_sources()
num_of = {f: {cp: n for n, cp in m.items()} for f, m in fam_map.items()}
doc = pymupdf.open(FONTS / "U3D000.pdf")
_index = {}


def locate(num):
    if not _index:
        for p in range(doc.page_count):
            for w in doc[p].get_text("words"):
                if re.match(r"^(TH|C|K|D)-", w[4]):
                    _index[w[4]] = (p, w[0], w[1])
    return _index.get(num)


def holes(mask_ink):
    bg = ~mask_ink
    reach = np.zeros_like(bg)
    reach[0, :], reach[-1, :] = bg[0, :], bg[-1, :]
    reach[:, 0] |= bg[:, 0]
    reach[:, -1] |= bg[:, -1]
    while True:
        g = reach.copy()
        g[1:] |= reach[:-1]; g[:-1] |= reach[1:]
        g[:, 1:] |= reach[:, :-1]; g[:, :-1] |= reach[:, 1:]
        g &= bg
        if (g == reach).all():
            return bg & ~reach
        reach = g


def tight(img):
    a = np.asarray(img.convert("L")) < 128
    ys, xs = np.where(a)
    if not len(ys):
        return img
    return img.crop((xs.min() - 4, ys.min() - 4, xs.max() + 5, ys.max() + 5))


def fit(img):
    img = tight(img)
    k = (S - 20) / max(img.size)
    img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    c = Image.new("RGB", (S, S), "white")
    c.paste(img, ((S - img.width) // 2, (S - img.height) // 2))
    return c


def row(fam, cp):
    num = num_of[fam].get(cp)
    loc = locate(num) if num else None
    if loc:
        p, x0, ytop = loc
        clip = pymupdf.Rect(x0 - 3, ytop - 25, x0 + 26, ytop - 0.6)
        pix = doc[p].get_pixmap(dpi=800, clip=clip)
        pdf = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        pdf = Image.new("RGB", (S, S), "white")
    pf = ImageFont.truetype(str(FONTS / "audit" / "_release" / REL[fam]), 1000)
    im = Image.new("L", (1300, 1300), 255)
    ImageDraw.Draw(im).text((150, 150), chr(cp), font=pf, fill=0)
    otf = fit(im.convert("RGB"))
    a = np.asarray(otf.convert("L")) < 140
    h = holes(a)
    mark = np.asarray(otf).copy()
    mark[h] = (230, 30, 30)
    lab = Image.new("RGB", (S, 40), "white")
    ImageDraw.Draw(lab).text((6, 4), f"{fam.upper()} U+{cp:X} {num or '无编号'}  红=封闭白区{int(h.sum())}px",
                             font=ImageFont.truetype(LAB, 22), fill=(0, 0, 0))
    body = Image.new("RGB", (S * 3 + 20, S), "white")
    body.paste(fit(pdf), (0, 0)); body.paste(otf, (S + 10, 0)); body.paste(Image.fromarray(mark), (2 * S + 20, 0))
    out = Image.new("RGB", (S * 3 + 20, S + 40), "white")
    out.paste(lab, (0, 0)); out.paste(body, (0, 40))
    return out


def main():
    name = sys.argv[1]
    items = [a.split(":") for a in sys.argv[2:]]
    rows = [row(f, int(c, 16)) for f, c in items]
    W = rows[0].width
    head = Image.new("RGB", (W, 44), "white")
    ImageDraw.Draw(head).text((6, 6), "左：码表 PDF 800dpi 原形　中：Release OTF　右：OTF 封闭白区标红",
                              font=ImageFont.truetype(LAB, 26), fill=(0, 0, 0))
    out = Image.new("RGB", (W, 44 + sum(r.height for r in rows)), "white")
    out.paste(head, (0, 0))
    y = 44
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    dst = FONTS / "audit" / "证据" / name
    out.save(dst)
    print(dst.relative_to(FONTS))


if __name__ == "__main__":
    main()
