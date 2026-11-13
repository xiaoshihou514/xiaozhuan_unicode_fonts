import json, glob, re, statistics
from collections import defaultdict
all_paths = defaultdict(dict)
for fn in glob.glob('build_svg/paths_*.json'):
    d = json.loads(open(fn).read())
    for fam, m in d.items():
        all_paths[fam].update(m)
d = all_paths['ccz']['251499']
xs, ys = [], []
pat = re.compile(r'([MmLlCcZz])\s*((?:-?[\d.]+(?:[,\s]-?[\d.]+)*)*)')
for c, v in pat.findall(d):
    n = [float(x) for x in re.findall(r'-?[\d.]+', v)]
    xs += n[0::2]
    ys += n[1::2]
print(f"采样点 {len(xs)} 个")
hs = []
for dd in list(all_paths['ccz'].values())[:400]:
    yy = [float(n) for n in re.findall(r'-?[\d.]+', dd)][1::2]
    if yy:
        hs.append(max(yy) - min(yy))
scale = 2048 * 0.75 / statistics.median(hs)
print(f"raw svg 系: x[{min(xs):.1f},{max(xs):.1f}] y[{min(ys):.1f},{max(ys):.1f}] scale={scale:.2f}")
# pen 系（y 翻转）：x 同，y 取负
print(f"归一前 pen 系 x: [{min(xs)*scale:.0f},{max(xs)*scale:.0f}]  宽 {(max(xs)-min(xs))*scale:.0f}")
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
f = TTFont('说文小篆-陈昌治本.otf', recalcBBoxes=False)
gs = f.getGlyphSet()
gn = f.getBestCmap()[251499]
bp = BoundsPen(gs)
gs[gn].draw(bp)
b = bp.bounds
print(f"成品 {gn}: bbox={tuple(round(v) for v in b)} 中心={(b[0]+b[2])/2/2048:.3f}em 步进={f['hmtx'][gn][0]}")
# 期望位置：w=(max-min)*scale, s2=min(0.96*2048/h, 0.98*2048/w)
w = (max(xs)-min(xs))*scale
h = (max(ys)-min(ys))*scale
s2 = min(0.96*2048/h, 0.98*2048/w)
tx = 0.5*2048 - w*s2/2 - min(xs)*scale*s2
print(f"期望 bbox x: [{tx:.0f},{tx+w*s2:.0f}] 中心 {0.5*2048}")
