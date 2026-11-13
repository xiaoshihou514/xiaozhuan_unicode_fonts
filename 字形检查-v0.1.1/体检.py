#!/usr/bin/env python3
"""v0.1.1 全量字形体检（numpy 向量化版）：四款×全 cmap。
检测：空字形、微小封闭孔洞（斑洞疑似）。
封闭孔洞：对 bbox 二值图从边界洪灌背景（scipy 不在则用 numpy BFS 逐行扫描法，
此处用「行列穿透 + 迭代膨胀」的向量化泛洪）。
"""
import sys
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

SIZE = 96
FONTS = ["../说文小篆-陈昌治本.otf", "../说文小篆-段玉裁本.otf",
         "../说文小篆-藤花树本.otf", "../说文小篆-徐锴本.otf"]

def flood_outside(mask):
    """mask: True=背景。返回从边界可达的背景布尔图。"""
    h, w = mask.shape
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

for fp in FONTS:
    tt = TTFont(fp)
    cmap = tt.getBestCmap()
    chars = [chr(cp) for cp in sorted(cmap) if cp >= 0x20000]
    tt.close()
    pf = ImageFont.truetype(fp, SIZE)
    empty, pinhole, ok = [], [], 0
    for ch in chars:
        img = Image.new("L", (SIZE, SIZE), 255)
        ImageDraw.Draw(img).text((SIZE * 0.15, SIZE * 0.15), ch,
                                 font=pf, fill=0)
        a = np.asarray(img) < 140          # True=墨
        ink = int(a.sum())
        if ink < 4:
            empty.append(ch); continue
        ys, xs = np.where(a)
        sub = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
        outside = flood_outside(~sub)
        holes_px = int((~sub & ~outside).sum())
        bbox_area = sub.size
        if holes_px and holes_px < max(6, bbox_area * 0.004):
            pinhole.append(ch)
        else:
            ok += 1
    print(f"{fp}: cmap {len(chars)} | 正常 {ok} | 空字形 {len(empty)} "
          f"| 斑洞疑似 {len(pinhole)}", flush=True)
    with open("体检报告.txt", "a", encoding="utf-8") as f:
        f.write(f"== {fp} ==\n")
        if empty:
            f.write("  空字形: " + " ".join(
                f"{c}(U+{ord(c):X})" for c in empty) + "\n")
        if pinhole:
            f.write("  斑洞疑似: " + " ".join(
                f"{c}(U+{ord(c):X})" for c in pinhole) + "\n")
        if not empty and not pinhole:
            f.write("  全部正常\n")
        f.write("\n")
print("体检完成，见 体检报告.txt")
