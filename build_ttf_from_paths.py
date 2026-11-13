#!/usr/bin/env python3
"""從 build_fonts_svg.py 產出的矢量 path 構建四款說文小篆字體（交付用中文名 OTF）。

本步驟自包含：靜態映射表（data/）供第二、三層 cmap，度量歸一直接在
建字階段完成（精確墨跡輪廓定位，含控制點的存儲 bbox 不可作依據）。
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen

ROOT = Path(__file__).parent
OUTDIR = ROOT / "build_svg"
from fontpaths import load_seal_sources, load_modern_map   # noqa: E402

UPEM = 2048
MAX_ERR = 1.0
# 度量歸一常量（視覺居中以精確墨跡輪廓為準）
INK_H = 0.96   # 目標墨跡高度 / em
INK_W = 0.98   # 目標墨跡寬度上限 / em
TOP = 0.86     # 墨跡頂 / em（baseline 之上）
BOT = -0.10    # 墨跡底 / em

FAMS = {
    "thx": dict(tag="THX", zh="藤花树本"),
    "ccz": dict(tag="CCZ", zh="陈昌治本"),
    "qjz": dict(tag="QJZ", zh="徐锴本"),
    "dyc": dict(tag="DYC", zh="段玉裁本"),
}

# SVG path（y 向下、基線 0）→ fontTools pen（y 向上）
class SvgToPen:
    """把 pdftocairo path d 畫到 pen，y 翻轉 + 縮放。"""
    CMDS = set("MLCZHV")

    def __init__(self, pen, scale):
        self.pen = pen
        self.s = scale
        self.cur = None
        self.start = None

    def _p(self, x, y):
        return (x * self.s, -y * self.s)

    def draw(self, d):
        import re
        raw = re.findall(r"([MmLlCcZz])\s*((?:-?[\d.]+(?:[,\s]-?[\d.]+)*)*)", d)
        segs = [(c.upper(), [float(n) for n in re.findall(r"-?[\d.]+", a)])
                for c, a in raw]
        # 剔除懸空的 M（無後續繪圖命令）
        while segs and segs[-1][0] == "M":
            segs.pop()

        pen, s = self.pen, self.s
        need_close = False
        for c, v in segs:
            if c == "M":
                if need_close:
                    pen.closePath()
                pen.moveTo(self._p(v[0], v[1]))
                for i in range(2, len(v), 2):
                    pen.lineTo(self._p(v[i], v[i + 1]))
                need_close = len(v) > 2
            elif c == "L":
                for i in range(0, len(v), 2):
                    pen.lineTo(self._p(v[i], v[i + 1]))
                need_close = True
            elif c == "C":
                for i in range(0, len(v), 6):
                    pen.curveTo(self._p(v[i], v[i + 1]),
                                self._p(v[i + 2], v[i + 3]),
                                self._p(v[i + 4], v[i + 5]))
                need_close = True
            elif c == "Z":
                pen.closePath()
                need_close = False
        if need_close:
            pen.closePath()


def build_family(fam, info, paths, mcjk_of, modern_map):
    tag, zh = info["tag"], info["zh"]
    cps = sorted(int(cp) for cp in paths)

    # 縮放：字形主高約 0.75em
    heights = []
    for d in list(paths.values())[:400]:
        ys = [float(n) for n in __import__("re").findall(r"-?[\d.]+", d)][1::2]
        if ys:
            heights.append(max(ys) - min(ys))
    h_med = statistics.median(heights)
    scale = UPEM * 0.75 / h_med

    # 同 path 去重共享字形
    uniq = {}
    cp_glyph = {}
    for cp in cps:
        d = paths[str(cp)]
        if d not in uniq:
            uniq[d] = f"u{cp:X}"
        cp_glyph[cp] = uniq[d]

    glyph_order = [".notdef"]
    glyphs_ttf, cs, cmap_glyph = {}, {}, {}
    metrics = {}
    bad = 0
    for d, gname in uniq.items():
        try:
            bp = BoundsPen(None)
            SvgToPen(bp, scale).draw(d)
            if not bp.bounds:
                raise ValueError("空輪廓")
            x0, _, x1, _ = bp.bounds
            ttpen = TTGlyphPen(None)
            SvgToPen(Cu2QuPen(ttpen, MAX_ERR, reverse_direction=True), scale).draw(d)
            glyphs_ttf[gname] = ttpen.glyph()
            glyph_order.append(gname)
            metrics[gname] = (int(round(x1 + 0.1 * UPEM)), int(round(x0)))
        except Exception as e:
            bad += 1
            if bad <= 3:
                print(f"  跳過壞字形 {gname}: {e}", file=sys.stderr)
    if bad:
        print(f"  共跳過 {bad} 個壞字形", file=sys.stderr)
    glyphs_ttf[".notdef"] = TTGlyphPen(None).glyph()
    cs[".notdef"] = T2CharStringPen(UPEM, None).getCharString()
    metrics[".notdef"] = (UPEM, 0)
    cmap_glyph = {cp: g for cp, g in cp_glyph.items() if g in glyphs_ttf}

    # 三層 cmap：小篆區／隸定字／通行字（靜態映射表，自包含）
    cmap = {}
    for cp, g in cmap_glyph.items():
        cmap[cp] = g
        mc = mcjk_of.get(cp)
        if mc:
            cmap.setdefault(ord(mc), g)
    for code, cp in modern_map.items():
        g = cmap_glyph.get(cp)
        if g:
            cmap.setdefault(code, g)

    fam_en = f"Shuowen Seal {tag}"
    fam_zh = f"说文小篆-{zh}"
    ps = f"ShuowenSeal{tag}-Regular"

    # ── 1) 先落盤編譯 TTF（粗縮放輪廓；歸一在編譯後進行，
    #    未編譯的 glyf 對象上直接讀取會得到錯位的字形容器——歷史缺陷）
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs_ttf)
    glyf_tbl = fb.font["glyf"]
    for g in glyphs_ttf.values():
        g.recalcBounds(glyf_tbl)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=int(TOP * UPEM), descent=int(BOT * UPEM))
    fb.setupNameTable({"familyName": fam_en, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=int(TOP * UPEM), sTypoDescender=int(BOT * UPEM),
                usWinAscent=int(TOP * UPEM), usWinDescent=int(-BOT * UPEM))
    fb.setupPost()
    tmp_ttf = ROOT / f".build-{tag}.ttf"
    fb.save(tmp_ttf)

    # ── 2) 重載編譯後的字體做輪廓疊加化（union）
    from fontTools.ttLib.removeOverlaps import removeOverlaps
    from fontTools.pens.boundsPen import BoundsPen as _BP
    ttf = TTFont(str(tmp_ttf))
    # ── 2) 编译后度量归一（两段式；在已编译字形上按精确墨迹轮廓定位，
    #    含控制点的存储 bbox 不可作为依据）。归一后编译重载，再叠加化。
    gs = ttf.getGlyphSet()
    glyf = ttf["glyf"]
    hmtx = ttf["hmtx"]
    n_scaled = 0
    for name in glyph_order:
        gobj = glyf[name]
        if getattr(gobj, "numberOfContours", 0) == 0:
            hmtx[name] = (UPEM, hmtx[name][1])
            continue
        bpn = _BP(gs)
        gs[name].draw(bpn)
        if not bpn.bounds:
            continue
        rx0, ry0, rx1, ry1 = bpn.bounds
        w, h = rx1 - rx0, ry1 - ry0
        if w <= 0 or h <= 0:
            continue
        s2 = min(INK_H * UPEM / h, INK_W * UPEM / w)
        if abs(s2 - 1.0) > 0.01:
            n_scaled += 1
        tx = 0.5 * UPEM - w * s2 / 2 - rx0 * s2
        ty = TOP * UPEM - ry1 * s2
        npen = TTGlyphPen(gs)
        tpen = TransformPen(npen, (s2, 0, 0, s2, tx, ty))
        gs[name].draw(tpen)
        glyf[name] = npen.glyph()
        glyf[name].recalcBounds(glyf)
        hmtx[name] = (UPEM, glyf[name].xMin)
    print(f"  歸一：縮放 {n_scaled} 字形，全角步進 {len(glyph_order)}", file=sys.stderr)
    tmp2 = ROOT / f".norm-{tag}.ttf"
    ttf.save(str(tmp2))
    ttf = TTFont(str(tmp2))

    # ── 3) 輪廓疊加化（union）
    removeOverlaps(ttf)

    # ── 3) 逐字自檢：疊加化後精確墨跡中心應仍在 0.5em（閾值 2% em），
    #    失敗即構建缺陷，直接報錯定位（不允許帶病交付）。
    gs = ttf.getGlyphSet()
    n_off = 0
    for name in glyph_order[1:]:
        bpc = _BP(gs)
        gs[name].draw(bpc)
        if bpc.bounds:
            off = ((bpc.bounds[0] + bpc.bounds[2]) / 2 - UPEM / 2) / UPEM
            if abs(off) > 0.02:
                n_off += 1
                if n_off <= 5:
                    print(f"  [自檢] {name} 中心偏 {off:+.1%}em", file=sys.stderr)
    if n_off:
        sys.exit(f"{fam_zh}: {n_off} 字形居中超阈，拒绝交付")

    # ── 4) CFF：從疊加化後的 TTF 輪廓轉三次（兩式幾何一致）
    cs = {}
    for name in glyph_order:
        t2 = T2CharStringPen(UPEM, None)
        gs[name].draw(t2)
        cs[name] = t2.getCharString()

    # name 表：中英雙份家族名＋中文法定聲明（PostScript 名按規範保 ASCII）
    for lang in (0x409, 0x804):
        ttf["name"].setName(fam_zh if lang == 0x804 else fam_en, 1, 3, 1, lang)
        ttf["name"].setName("Regular" if lang == 0x409 else "常规", 2, 3, 1, lang)
        ttf["name"].setName(fam_zh if lang == 0x804 else fam_en, 4, 3, 1, lang)
        ttf["name"].setName(ps, 6, 3, 1, lang)
    ttf["name"].setName("字形提取自 Unicode 18.0 碼表 U3D000.pdf，僅供研究使用", 13, 3, 1, 0x409)
    ttf["OS/2"].fsType = 0

    # ── 5) 交付物僅 CFF OTF：複用 cmap／度量／name，輪廓為疊加化後的三次曲線
    out = ROOT / f"{fam_zh}.otf"
    fb2 = FontBuilder(UPEM, isTTF=False)
    fb2.setupGlyphOrder(glyph_order)
    fb2.setupCharacterMap(cmap)
    fb2.setupCFF(ps, {"FullName": fam_en}, cs, {})
    fb2.setupHorizontalMetrics({n: ttf["hmtx"][n] for n in glyph_order})
    for tag_ in ("hhea", "OS/2", "name", "post"):
        fb2.font[tag_] = ttf[tag_]
    fb2.save(out)
    tmp_ttf.unlink()
    print(f"  {out.name}: {len(glyphs_ttf)} 字形, cmap {len(cmap)} 條", file=sys.stderr)


def main():
    import glob
    files = sorted(glob.glob(str(OUTDIR / "paths_*.json")))
    assert files, "缺少 paths json（先運行 build_fonts_svg.py）"
    all_paths = defaultdict(dict)
    for fn in files:
        d = json.loads(Path(fn).read_text())
        for fam, m in d.items():
            all_paths[fam].update(m)

    seal_map, mcjk_of = load_seal_sources()
    modern = load_modern_map()
    print(f"通行字層 {len(modern)}（data/modern_map.tsv）", file=sys.stderr)

    for fam, info in FAMS.items():
        build_family(fam, info, all_paths.get(fam, {}), mcjk_of, modern)


if __name__ == "__main__":
    main()
