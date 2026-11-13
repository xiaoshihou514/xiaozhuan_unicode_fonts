#!/usr/bin/env python3
"""码表 PDF 原形 / v0.1.1 / v0.1.3 三栏对照（只读，输出到 audit/证据/复验/）。

用法：uv run --offline python audit/工具/复验/三版对照.py 输出名.png 家:码位 ...
每行左＝PDF 800dpi 裁切；中＝v0.1.1；右＝v0.1.3（封闭白区标红）。
"""
import re
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(FONTS))
from fontpaths import load_seal_sources   # noqa: E402

REL = {"ccz": "ShuowenSeal-ChenChangzhi.otf", "qjz": "ShuowenSeal-XuKai.otf",
       "dyc": "ShuowenSeal-DuanYucai.otf", "thx": "ShuowenSeal-TengHuaShu.otf"}
S = 330
LAB = "/home/xiaoshihou/.local/share/fonts/lxgw-wenkai-v1.522/LXGWWenKai-Medium.ttf"
fam_map, _ = load_seal_sources()
num_of = {f: {cp: n for n, cp in m.items()} for f, m in fam_map.items()}
doc = pymupdf.open(FONTS / "U3D000.pdf")
idx = {}
for p in range(doc.page_count):
    for w in doc[p].get_text("words"):
        if re.match(r"^(TH|C|K|D)-", w[4]):
            idx[w[4]] = (p, w[0], w[1])


def holes(ink):
    bg = ~ink
    reach = np.zeros_like(bg)
    reach[0, :], reach[-1, :] = bg[0, :], bg[-1, :]
    reach[:, 0] |= bg[:, 0]; reach[:, -1] |= bg[:, -1]
    while True:
        g = reach.copy()
        g[1:] |= reach[:-1]; g[:-1] |= reach[1:]; g[:, 1:] |= reach[:, :-1]; g[:, :-1] |= reach[:, 1:]
        g &= bg
        if (g == reach).all():
            return bg & ~reach
        reach = g


def fit(img, mark=False):
    a = np.asarray(img.convert("L")) < 128
    ys, xs = np.where(a)
    if len(ys):
        img = img.crop((xs.min() - 4, ys.min() - 4, xs.max() + 5, ys.max() + 5))
    k = (S - 20) / max(img.size)
    img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    c = Image.new("RGB", (S, S), "white")
    c.paste(img.convert("RGB"), ((S - img.width) // 2, (S - img.height) // 2))
    if mark:
        arr = np.asarray(c).copy()
        arr[holes(np.asarray(c.convert("L")) < 140)] = (230, 30, 30)
        c = Image.fromarray(arr)
    return c


def glyph(font, cp):
    pf = ImageFont.truetype(str(font), 1000)
    im = Image.new("L", (1300, 1300), 255)
    ImageDraw.Draw(im).text((150, 150), chr(cp), font=pf, fill=0)
    return im


def row(fam, cp):
    num = num_of[fam].get(cp)
    p, x0, ytop = idx[num]
    pix = doc[p].get_pixmap(dpi=800, clip=pymupdf.Rect(x0 - 3, ytop - 25, x0 + 26, ytop - 0.6))
    pdf = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    a = fit(glyph(FONTS / "audit" / "_release" / REL[fam], cp), True)
    b = fit(glyph(FONTS / "audit" / "_release-v0.1.3" / REL[fam], cp), True)
    lab = Image.new("RGB", (S * 3 + 20, 36), "white")
    ImageDraw.Draw(lab).text((6, 4), f"{fam.upper()} U+{cp:X} {num}", font=ImageFont.truetype(LAB, 22), fill="black")
    body = Image.new("RGB", (S * 3 + 20, S), "white")
    body.paste(fit(pdf), (0, 0)); body.paste(a, (S + 10, 0)); body.paste(b, (2 * S + 20, 0))
    out = Image.new("RGB", (S * 3 + 20, S + 36), "white")
    out.paste(lab, (0, 0)); out.paste(body, (0, 36))
    return out


def main():
    rows = [row(f, int(c, 16)) for f, c in (a.split(":") for a in sys.argv[2:])]
    W = rows[0].width
    head = Image.new("RGB", (W, 40), "white")
    ImageDraw.Draw(head).text((6, 6), "左：码表 PDF 原形　中：v0.1.1　右：v0.1.3（红＝封闭白区）",
                              font=ImageFont.truetype(LAB, 24), fill="black")
    out = Image.new("RGB", (W, 40 + sum(r.height for r in rows)), "white")
    out.paste(head, (0, 0))
    y = 40
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    dst = FONTS / "audit" / "证据" / "复验" / sys.argv[1]
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    print(dst.relative_to(FONTS))


if __name__ == "__main__":
    main()
