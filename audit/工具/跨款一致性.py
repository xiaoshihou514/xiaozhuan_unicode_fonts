#!/usr/bin/env python3
"""跨款一致性：同一小篆码位四家字形应大体同构。对每个码位把各款字形
按墨迹包围盒归一到 48×48 光栅，计算两两交并比（IoU）；若某款与其余各款
IoU 都显著偏低、而其余各款彼此一致，则疑为「配错字形」（标注→use 匹配错位）。
输出 audit/数据/跨款离群.tsv。
"""
import itertools
from pathlib import Path

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[2]
REL = {"ccz": "ShuowenSeal-ChenChangzhi.otf", "qjz": "ShuowenSeal-XuKai.otf",
       "dyc": "ShuowenSeal-DuanYucai.otf", "thx": "ShuowenSeal-TengHuaShu.otf"}
N = 48


def raster(pf, ch):
    im = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(im).text((20, 20), ch, font=pf, fill=255)
    a = np.asarray(im)
    ys, xs = np.where(a > 100)
    if not len(ys):
        return None
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).resize((N, N), Image.BILINEAR)
    return np.asarray(im) > 100


def main():
    fonts = {k: (TTFont(str(FONTS / "audit" / "_release" / v)).getBestCmap(),
                 ImageFont.truetype(str(FONTS / "audit" / "_release" / v), 150)) for k, v in REL.items()}
    rows = []
    for cp in range(0x3D000, 0x3FC40):
        have = {k: raster(pf, chr(cp)) for k, (cm, pf) in fonts.items() if cp in cm}
        have = {k: v for k, v in have.items() if v is not None}
        if len(have) < 3:
            continue
        iou = {}
        for a, b in itertools.combinations(have, 2):
            i = (have[a] & have[b]).sum(); u = (have[a] | have[b]).sum()
            iou[(a, b)] = iou[(b, a)] = i / u if u else 0
        for k in have:
            others = [o for o in have if o != k]
            mine = max(iou[(k, o)] for o in others)
            rest = [iou[(a, b)] for a, b in itertools.combinations(others, 2)]
            rest_min = min(rest) if rest else 1
            if mine < 0.30 and rest_min > mine + 0.15:
                rows.append((k, f"U+{cp:X}", f"{mine:.2f}", f"{rest_min:.2f}"))
    out = FONTS / "audit" / "数据" / "跨款离群.tsv"
    out.write_text("款\t码位\t与他款最大IoU\t他款间最小IoU\n" + "\n".join("\t".join(r) for r in rows) + "\n",
                   encoding="utf-8")
    print(f"离群 {len(rows)} 条 → {out.relative_to(FONTS)}")


if __name__ == "__main__":
    main()
