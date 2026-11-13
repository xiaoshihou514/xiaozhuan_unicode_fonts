#!/usr/bin/env python3
"""字形水平居中回归检测：统计 OTF 中墨迹精确中心偏离 0.5em 超 2% 的字形。

用法：python check_centering.py [字体.otf ...]（缺省扫当前目录全部 OTF）
退出码：全部居中 0；存在超阈字形 1（供构建流水线把关）。
"""
import sys
from glob import glob

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

THRESH = 0.02   # 偏差阈值 / em


def check(fn: str) -> int:
    f = TTFont(fn, recalcBBoxes=False)
    upem = f["head"].unitsPerEm
    gs = f.getGlyphSet()
    bad = []
    n = 0
    for gn in gs.keys():
        bp = BoundsPen(gs)
        try:
            gs[gn].draw(bp)
        except Exception:
            continue
        if not bp.bounds:
            continue
        x0, _, x1, _ = bp.bounds
        n += 1
        off = ((x0 + x1) / 2 - upem / 2) / upem
        if abs(off) > THRESH:
            bad.append((gn, off))
    status = "通过" if not bad else f"超阈 {len(bad)} 个（最大 {max(abs(o) for _, o in bad):.2%}em）"
    print(f"{fn}: 检测 {n} 字形 → {status}")
    for gn, off in sorted(bad, key=lambda t: -abs(t[1]))[:12]:
        print(f"  {gn}: {off:+.2%}em")
    return 1 if bad else 0


def main() -> int:
    files = sys.argv[1:] or sorted(glob("*.otf"))
    if not files:
        print("未找到 OTF", file=sys.stderr)
        return 2
    return max(check(fn) for fn in files)


if __name__ == "__main__":
    sys.exit(main())
