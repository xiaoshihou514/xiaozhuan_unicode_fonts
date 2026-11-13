"""单字形复现：u3D66B 从 path 到叠加化各阶段的精确墨迹界。"""
import json, glob, re, statistics, sys
from collections import defaultdict
sys.path.insert(0, '.')
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from build_ttf_from_paths import SvgToPen, UPEM, MAX_ERR, INK_H, INK_W, TOP

all_paths = defaultdict(dict)
for fn in glob.glob('build_svg/paths_*.json'):
    d = json.loads(open(fn).read())
    for fam, m in d.items():
        all_paths[fam].update(m)
d = all_paths['ccz']['251499']

hs = []
for dd in list(all_paths['ccz'].values())[:400]:
    yy = [float(n) for n in re.findall(r'-?[\d.]+', dd)][1::2]
    if yy:
        hs.append(max(yy) - min(yy))
scale = UPEM * 0.75 / statistics.median(hs)

bp = BoundsPen(None)
SvgToPen(bp, scale).draw(d)
x0, y0, x1, y1 = bp.bounds
w, h = x1 - x0, y1 - y0
s2 = min(INK_H * UPEM / h, INK_W * UPEM / w)
tx = 0.5 * UPEM - w * s2 / 2 - x0 * s2
ty = TOP * UPEM - y1 * s2
M = (s2, 0, 0, s2, tx, ty)
print(f"精确墨迹界(pen系): [{x0:.1f},{x1:.1f}]×[{y0:.1f},{y1:.1f}]  w={w:.0f} h={h:.0f} s2={s2:.3f}")
print(f"变换后期望 x: [{x0*s2+tx:.1f},{x1*s2+tx:.1f}]")

ttpen = TTGlyphPen(None)
SvgToPen(Cu2QuPen(TransformPen(ttpen, M), MAX_ERR, reverse_direction=True), scale).draw(d)
g = ttpen.glyph()

fb = FontBuilder(UPEM, isTTF=True)
fb.setupGlyphOrder(['.notdef', 'u3D66B'])
from fontTools.pens.ttGlyphPen import TTGlyphPen as _TP
fb.setupGlyf({'.notdef': _TP(None).glyph(), 'u3D66B': g})
fb.setupHorizontalMetrics({'.notdef': (UPEM, 0), 'u3D66B': (UPEM, 0)})
from fontTools.ttLib.removeOverlaps import removeOverlaps
bp0 = BoundsPen({'.notdef': None, 'u3D66B': g}.__getitem__ and {'.notdef': __import__('fontTools.pens.ttGlyphPen', fromlist=['TTGlyphPen']).TTGlyphPen(None).glyph(), 'u3D66B': g}.values().__iter__().__next__ and {'u3D66B': g})
# 叠加化前实测
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen as _BP
gs_pre = {'.notdef': __import__('fontTools.pens.ttGlyphPen', fromlist=['TTGlyphPen']).TTGlyphPen(None).glyph(), 'u3D66B': g}
class FakeGS:
    def __init__(self, gs): self.gs = gs
    def __getitem__(self, k): return _GlyphW(self.gs[k])
    def keys(self): return self.gs.keys()
from fontTools.pens.basePen import BasePen
class _GlyphW:
    def __init__(self, g): self.g = g
    def draw(self, pen): self.g.draw(pen)
bp0 = BoundsPen(None)
fb.font["glyf"]["u3D66B"].draw(bp0, fb.font["glyf"])
print(f"Cu2Qu 后（叠加化前）实际 x: [{bp0.bounds[0]:.1f},{bp0.bounds[2]:.1f}]")
removeOverlaps(fb.font)
gs = fb.font.getGlyphSet()
bp2 = BoundsPen(gs)
gs['u3D66B'].draw(bp2)
b2 = bp2.bounds
print(f"叠加化后实际 x: [{b2[0]:.1f},{b2[2]:.1f}]  中心={(b2[0]+b2[2])/2:.0f}")
rp = __import__('fontTools.pens.recordingPen', fromlist=['RecordingPen']).RecordingPen()
gs['u3D66B'].draw(rp)
print("叠加化后轮廓数:", sum(1 for op, _ in rp.value if op == 'moveTo'))

rp2 = RecordingPen()
gs['u3D66B'].draw(rp2)
mv = [args for op, args in rp2.value if op == 'moveTo']
print("repro 各轮廓起点:", mv[:7])
