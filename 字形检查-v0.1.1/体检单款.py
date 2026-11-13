#!/usr/bin/env python3
"""单款字体体检（用法：体检单款.py <字体路径>）。方法与阈值见 体检方法说明.md。"""
import sys
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

fp = sys.argv[1]
SIZE = 96
tt = TTFont(fp)
cmap = tt.getBestCmap()
chars = [chr(cp) for cp in sorted(cmap) if cp >= 0x20000]
tt.close()
pf = ImageFont.truetype(fp, SIZE)

def flood_outside(mask):
    reach = np.zeros_like(mask)
    reach[0, :] = mask[0, :]; reach[-1, :] = mask[-1, :]
    reach[:, 0] |= mask[:, 0]; reach[:, -1] |= mask[:, -1]
    while True:
        grow = reach.copy()
        grow[1:, :] |= reach[:-1, :]
        grow[:-1, :] |= reach[1:, :]
        grow[:, 1:] |= reach[:, :-1]
        grow[:, :-1] |= reach[:, 1:]
        grow &= mask
        if (grow == reach).all():
            return reach
        reach = grow

empty, pinhole, ok = [], [], 0
for ch in chars:
    img = Image.new("L", (SIZE, SIZE), 255)
    ImageDraw.Draw(img).text((SIZE * 0.15, SIZE * 0.15), ch, font=pf, fill=0)
    a = np.asarray(img) < 140
    if int(a.sum()) < 4:
        empty.append(ch); continue
    ys, xs = np.where(a)
    sub = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    holes_px = int((~sub & ~flood_outside(~sub)).sum())
    bbox_area = sub.size
    if holes_px and holes_px < max(6, bbox_area * 0.004):
        pinhole.append(ch)
    else:
        ok += 1
print(f"{fp}: cmap {len(chars)} | 正常 {ok} | 空字形 {len(empty)} | 斑洞疑似 {len(pinhole)}")
with open("体检报告.txt", "a", encoding="utf-8") as f:
    f.write(f"== {fp} ==\n")
    if empty:
        f.write("  空字形: " + " ".join(f"{c}(U+{ord(c):X})" for c in empty) + "\n")
    if pinhole:
        f.write("  斑洞疑似: " + " ".join(f"{c}(U+{ord(c):X})" for c in pinhole) + "\n")
    if not empty and not pinhole:
        f.write("  全部正常\n")
    f.write("\n")
