#!/usr/bin/env python3
"""独立审计：四款 OTF 全量几何扫描（只读，结果写 audit/数据/）。

用法（在 fonts/ 下）：
  UV_CACHE_DIR=$PWD/.uv-cache uv run --offline python audit/工具/几何审计.py [release|local]
  release = audit/_release/ 下 v0.1.1 Release 附件（默认，交付物基线）
  local   = fonts/ 根目录四款 OTF（其中三款为 WIP 代码构建，见报告）

逐字产出（每款一行一字）：
  cmap 层级、空字形、墨迹包围盒、水平/垂直中心偏差、缩放约束维度、
  轮廓数、孔洞（反向轮廓）数与最小孔洞面积、碎屑（极小外轮廓）数、
  残余自交（再次 simplify 面积变化）、与码表源路径的拓扑/面积一致性。
"""
import csv
import json
import sys
from pathlib import Path

import pathops
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FONTS))
from build_ttf_from_paths import SvgToPen          # noqa: E402  只读复用解析器
from fontpaths import load_modern_map, load_seal_sources   # noqa: E402

FAMS = [  # (paths 键, 中文名, Release 附件名)
    ("ccz", "陈昌治本", "ShuowenSeal-ChenChangzhi.otf"),
    ("qjz", "徐锴本", "ShuowenSeal-XuKai.otf"),
    ("dyc", "段玉裁本", "ShuowenSeal-DuanYucai.otf"),
    ("thx", "藤花树本", "ShuowenSeal-TengHuaShu.otf"),
]
FACE_TOP, FACE_BOT = 0.86, -0.10
FACE_MID = (FACE_TOP + FACE_BOT) / 2       # 0.38em
EM2 = 2048.0 ** 2


def skpath_from_pen_drawer(draw):
    p = pathops.Path()
    draw(p.getPen())
    return p


def topo(path, norm):
    """path 已为非零规则；返回 (面积/em², 外轮廓数, 孔洞面积列表/em², 碎屑数)。
    norm：面积换算到 em² 的系数。"""
    try:
        s = pathops.simplify(path)
    except Exception:
        return None
    cs = list(s.contours)
    if not cs:
        return (0.0, 0, [], 0)
    big = max(cs, key=lambda c: c.area)
    outers = [c for c in cs if c.clockwise == big.clockwise]
    holes = [c.area * norm for c in cs if c.clockwise != big.clockwise]
    specks = sum(1 for c in outers if c.area * norm < 2e-4)   # <0.02% em²
    return (s.area * norm, len(outers), sorted(holes), specks)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "release"
    out_dir = FONTS / "audit" / "数据"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = json.loads((FONTS / "build_svg" / "paths_1-189.json").read_text())
    _, mcjk_of = load_seal_sources()
    modern = load_modern_map()

    for fam, zh, rel in FAMS:
        fn = (FONTS / "audit" / "_release" / rel) if mode == "release" \
            else (FONTS / f"说文小篆-{zh}.otf")
        ft = TTFont(str(fn))
        upem = ft["head"].unitsPerEm
        cmap = ft.getBestCmap()
        gs = ft.getGlyphSet()
        hmtx = ft["hmtx"]
        # cmap 层级标注
        mc_set = {ord(c) for c in mcjk_of.values()}
        layer = {}
        for cp in cmap:
            if 0x3D000 <= cp <= 0x3FC3F:
                layer[cp] = "篆"
            elif cp in mc_set:
                layer[cp] = "隸"
            elif cp in modern:
                layer[cp] = "通"
            else:
                layer[cp] = "？"

        src = paths.get(fam, {})
        rows = []
        cache = {}
        for cp in sorted(cmap):
            g = cmap[cp]
            if g in cache:
                r = dict(cache[g]); r.update(cp=f"U+{cp:04X}", 层=layer[cp])
                rows.append(r)
                continue
            bp = BoundsPen(gs)
            gs[g].draw(bp)
            r = {"cp": f"U+{cp:04X}", "层": layer[cp], "glyph": g,
                 "步进": hmtx[g][0]}
            if not bp.bounds:
                r["空"] = 1
                cache[g] = r; rows.append(r); continue
            x0, y0, x1, y1 = bp.bounds
            w, h = (x1 - x0) / upem, (y1 - y0) / upem
            r.update(空=0, x0=round(x0), y0=round(y0), x1=round(x1), y1=round(y1),
                     宽=round(w, 4), 高=round(h, 4),
                     水平偏=round(((x0 + x1) / 2 - upem / 2) / upem, 4),
                     垂直偏=round(((y0 + y1) / 2) / upem - FACE_MID, 4),
                     约束="宽" if abs(w - 0.98) < 0.004 and h < 0.955 else "高")
            fp = skpath_from_pen_drawer(gs[g].draw)
            t = topo(fp, 1.0 / EM2)
            # 残余自交/重叠：交付轮廓再 simplify，面积应不变
            r["残余重叠"] = round(abs(fp.area / EM2 - t[0]), 6) if t else -1
            if t:
                r.update(面积=round(t[0], 5), 外轮廓=t[1], 孔洞=len(t[2]),
                         最小孔=round(t[2][0], 6) if t[2] else "",
                         碎屑=t[3])
            # 源路径对照（仅小篆区本字）
            d = src.get(str(int(g[1:], 16))) if g.startswith("u") else None
            if d:
                sp = pathops.Path()
                SvgToPen(sp.getPen(), 1.0).draw(d)
                sb = sp.bounds
                sw, sh = sb[2] - sb[0], sb[3] - sb[1]
                k = (x1 - x0) / sw if sw else 0      # 源→字体的线性比例
                ts = topo(sp, k * k / EM2)
                if ts:
                    r.update(源面积=round(ts[0], 5), 源外轮廓=ts[1], 源孔洞=len(ts[2]),
                             源最小孔=round(ts[2][0], 6) if ts[2] else "",
                             源碎屑=ts[3],
                             源宽高比=round(sw / sh, 4) if sh else "",
                             宽高比=round(w / h, 4) if h else "")
                    if t:
                        r["面积差"] = round((t[0] - ts[0]) / ts[0], 4) if ts[0] else ""
            cache[g] = r
            rows.append(r)
        keys = ["cp", "层", "glyph", "空", "步进", "x0", "y0", "x1", "y1", "宽", "高",
                "水平偏", "垂直偏", "约束", "面积", "外轮廓", "孔洞", "最小孔", "碎屑",
                "残余重叠", "源面积", "源外轮廓", "源孔洞", "源最小孔", "源碎屑",
                "面积差", "宽高比", "源宽高比"]
        of = out_dir / f"{mode}-{zh}.tsv"
        with open(of, "w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, keys, delimiter="\t", extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)
        print(f"{zh}: {len(rows)} 条 → {of.relative_to(FONTS)}", flush=True)


if __name__ == "__main__":
    main()
