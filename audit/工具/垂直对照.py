#!/usr/bin/env python3
"""扁宽字形垂直位置可视化：每格画出全角框（灰）、字面区 [−0.10, +0.86]em（蓝虚线）
与字面中线 0.38em（红线），字形按字体原始度量摆放（不做任何重定位）。

用法：uv run --offline python audit/工具/垂直对照.py 输出.png 字体1.otf[=标签] ... -- 码位 ...
"""
import sys
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[2]
LAB = "/home/xiaoshihou/.local/share/fonts/lxgw-wenkai-v1.522/LXGWWenKai-Medium.ttf"
C = 220          # 每格像素（=1em）
PAD = 30


class PolyPen(BasePen):
    def __init__(self, gs, f):
        super().__init__(gs)
        self.f, self.polys, self.cur = f, [], []

    def _moveTo(self, p):
        self.cur = [self.f(p)]

    def _lineTo(self, p):
        self.cur.append(self.f(p))

    def _curveToOne(self, a, b, c):
        p0 = self._getCurrentPoint()
        for i in range(1, 9):
            t = i / 8
            mt = 1 - t
            x = mt**3*p0[0] + 3*mt*mt*t*a[0] + 3*mt*t*t*b[0] + t**3*c[0]
            y = mt**3*p0[1] + 3*mt*mt*t*a[1] + 3*mt*t*t*b[1] + t**3*c[1]
            self.cur.append(self.f((x, y)))

    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(self.cur)
        self.cur = []


def main():
    args = sys.argv[1:]
    out = args[0]
    k = args.index("--")
    fonts = [a.split("=") if "=" in a else (a, Path(a).stem) for a in args[1:k]]
    cps = [int(c, 16) for c in args[k + 1:]]
    W = PAD * 2 + 200 + len(cps) * (C + 20)
    H = PAD * 2 + len(fonts) * (C + 40)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lf = ImageFont.truetype(LAB, 22)
    for i, (fn, lab) in enumerate(fonts):
        ft = TTFont(fn)
        upem = ft["head"].unitsPerEm
        cmap = ft.getBestCmap()
        gs = ft.getGlyphSet()
        top = PAD + i * (C + 40) + 30
        d.text((PAD, top + C // 2 - 12), lab, font=lf, fill="black")
        for j, cp in enumerate(cps):
            left = PAD + 200 + j * (C + 20)
            # 全角框：基线在 0，框取 [−0.12, 0.88]（与常见 CJK 体例相近，仅作参照）
            ytop_em = 0.88
            def tf(p, left=left, top=top):
                return (left + p[0] / upem * C, top + (ytop_em - p[1] / upem) * C)
            d.rectangle([left, top, left + C, top + C], outline=(170, 170, 170))
            for yem, col in ((0.86, (60, 90, 220)), (-0.10, (60, 90, 220))):
                y = top + (ytop_em - yem) * C
                for x in range(left, left + C, 8):
                    d.line([(x, y), (x + 4, y)], fill=col)
            ym = top + (ytop_em - 0.38) * C
            d.line([(left, ym), (left + C, ym)], fill=(220, 40, 40))
            g = cmap.get(cp)
            if g:
                pen = PolyPen(gs, tf)
                gs[g].draw(pen)
                # 交付轮廓已叠加化（无重叠），奇偶填充与非零等价：用异或累积
                acc = Image.new("1", img.size, 0)
                for poly in pen.polys:
                    m = Image.new("1", img.size, 0)
                    ImageDraw.Draw(m).polygon(poly, fill=1)
                    acc = Image.frombytes("1", img.size, bytes(a ^ b for a, b in zip(acc.tobytes(), m.tobytes())))
                img.paste((0, 0, 0), mask=acc)
            d.text((left + 4, top + C + 2), f"U+{cp:X}", font=ImageFont.truetype(LAB, 16), fill=(90, 90, 90))
    d.text((PAD, 4), "灰框＝全角参照；蓝虚线＝字面区顶 0.86em/底 −0.10em；红线＝字面中线 0.38em（墨迹中心应落在红线上）",
           font=ImageFont.truetype(LAB, 18), fill="black")
    img.save(FONTS / "audit" / "证据" / out)
    print("audit/证据/" + out)


if __name__ == "__main__":
    main()
