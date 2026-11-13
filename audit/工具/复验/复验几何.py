#!/usr/bin/env python3
"""发布后复验（v0.1.3）：逐字几何普查，与首轮审计 几何审计.py 同口径。

与首轮差异：字体目录、源路径文件可配置；源路径对照时同时给出
「剔碎屑前」与「交付」两种拓扑，用于核验碎屑剔除是否误删设计镂空。

用法（fonts/ 下）：
  UV_CACHE_DIR=$PWD/.uv-cache PYTHONDONTWRITEBYTECODE=1 \
    uv run --offline python audit/工具/复验/复验几何.py audit/_release-v0.1.3 build_svg/paths_all.json v013
"""
import csv
import json
import sys
from pathlib import Path

import pathops
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(FONTS))
from build_ttf_from_paths import SvgToPen          # noqa: E402  只读复用源路径解析器
from fontpaths import load_modern_map, load_seal_sources   # noqa: E402

FAMS = [("ccz", "陈昌治本", "ShuowenSeal-ChenChangzhi.otf"),
        ("qjz", "徐锴本", "ShuowenSeal-XuKai.otf"),
        ("dyc", "段玉裁本", "ShuowenSeal-DuanYucai.otf"),
        ("thx", "藤花树本", "ShuowenSeal-TengHuaShu.otf")]
FACE_MID = 0.38
EM2 = 2048.0 ** 2


def topo(path, norm):
    try:
        s = pathops.simplify(path)
    except Exception:
        return None
    cs = list(s.contours)
    if not cs:
        return (0.0, 0, [], 0)
    big = max(cs, key=lambda c: c.area)
    outers = [c for c in cs if c.clockwise == big.clockwise]
    holes = sorted(c.area * norm for c in cs if c.clockwise != big.clockwise)
    specks = sum(1 for c in outers if c.area * norm < 2e-4)
    return (s.area * norm, len(outers), holes, specks)


def main():
    fdir, pfile, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    out_dir = FONTS / "audit" / "数据" / "复验"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = json.loads((FONTS / pfile).read_text())
    _, mcjk_of = load_seal_sources()
    modern = load_modern_map()
    mc_set = {ord(c) for c in mcjk_of.values()}
    for fam, zh, rel in FAMS:
        ft = TTFont(str(FONTS / fdir / rel))
        upem = ft["head"].unitsPerEm
        cmap = ft.getBestCmap()
        gs = ft.getGlyphSet()
        hmtx = ft["hmtx"]
        src = paths.get(fam, {})
        cache, rows = {}, []
        for cp in sorted(cmap):
            g = cmap[cp]
            lay = "篆" if 0x3D000 <= cp <= 0x3FC3F else "隸" if cp in mc_set \
                else "通" if cp in modern else "？"
            if g in cache:
                r = dict(cache[g]); r.update(cp=f"U+{cp:04X}", 层=lay); rows.append(r)
                continue
            bp = BoundsPen(gs); gs[g].draw(bp)
            r = {"cp": f"U+{cp:04X}", "层": lay, "glyph": g, "步进": hmtx[g][0]}
            if not bp.bounds:
                r["空"] = 1; cache[g] = r; rows.append(r); continue
            x0, y0, x1, y1 = bp.bounds
            w, h = (x1 - x0) / upem, (y1 - y0) / upem
            r.update(空=0, 宽=round(w, 4), 高=round(h, 4),
                     水平偏=round(((x0 + x1) / 2 - upem / 2) / upem, 4),
                     垂直偏=round((y0 + y1) / 2 / upem - FACE_MID, 4),
                     约束="宽" if abs(w - 0.98) < 0.004 and h < 0.955 else "高")
            fp = pathops.Path(); gs[g].draw(fp.getPen())
            t = topo(fp, 1.0 / EM2)
            if t:
                r.update(面积=round(t[0], 5), 外轮廓=t[1], 孔洞=len(t[2]),
                         最小孔=round(t[2][0], 6) if t[2] else "", 碎屑=t[3],
                         残余重叠=round(abs(fp.area / EM2 - t[0]), 6))
            d = src.get(str(int(g[1:], 16))) if g.startswith("u") else None
            if d and t:
                sp = pathops.Path(); SvgToPen(sp.getPen(), 1.0).draw(d)
                sb = sp.bounds
                ts = topo(sp, 1.0)
                if ts and ts[0]:
                    # 以面积比例归一（交付剔了碎屑，包围盒不可直接比）
                    k2 = t[0] / ts[0]
                    holes_s = [a * k2 for a in ts[2]]
                    r.update(源外轮廓=ts[1], 源孔洞=len(ts[2]),
                             源最小孔=round(holes_s[0], 6) if holes_s else "",
                             源碎屑=ts[3],
                             源大孔=sum(1 for a in holes_s if a >= 2e-4),
                             大孔=sum(1 for a in t[2] if a >= 2e-4))
            cache[g] = r
            rows.append(r)
        keys = ["cp", "层", "glyph", "空", "步进", "宽", "高", "水平偏", "垂直偏", "约束",
                "面积", "外轮廓", "孔洞", "最小孔", "碎屑", "残余重叠",
                "源外轮廓", "源孔洞", "源最小孔", "源碎屑", "源大孔", "大孔"]
        of = out_dir / f"{tag}-{zh}.tsv"
        with open(of, "w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, keys, delimiter="\t", extrasaction="ignore")
            wr.writeheader(); wr.writerows(rows)
        print(f"{zh}: {len(rows)} 条 → {of.relative_to(FONTS)}", flush=True)


if __name__ == "__main__":
    main()
