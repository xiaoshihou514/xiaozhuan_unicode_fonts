#!/usr/bin/env python3
"""從 build_fonts_svg.py 產出的矢量 path 構建四款說文小篆字體（TTF+OTF）。"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen

ROOT = Path(__file__).parent
OUTDIR = ROOT / "build_svg"
from fontpaths import find_seal_db   # noqa: E402
DB = find_seal_db()
UPEM = 2048
MAX_ERR = 1.0

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
    glyphs, metrics, cmap_glyph = {}, {}, {}
    bad = 0
    for d, gname in uniq.items():
        try:
            ttpen = TTGlyphPen(None)
            SvgToPen(Cu2QuPen(ttpen, MAX_ERR, reverse_direction=True), scale).draw(d)
            g = ttpen.glyph()
            bp = BoundsPen(None)
            SvgToPen(bp, scale).draw(d)
            if bp.bounds:
                x0, _, x1, _ = bp.bounds
            else:
                raise ValueError("空輪廓")
            glyphs[gname] = g
            glyph_order.append(gname)
            adv = int(round(x1 + 0.1 * UPEM))
            metrics[gname] = (adv, int(round(x0)))
        except Exception as e:
            bad += 1
            if bad <= 3:
                print(f"  跳過壞字形 {gname}: {e}", file=sys.stderr)
    if bad:
        print(f"  共跳過 {bad} 個壞字形", file=sys.stderr)
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    metrics[".notdef"] = (UPEM // 2, 0)
    cmap_glyph = {cp: g for cp, g in cp_glyph.items() if g in glyphs}

    fb = FontBuilder(UPEM, isTTF=True)
    fam_en = f"Shuowen Seal {tag}"
    fam_zh = f"说文小篆-{zh}"
    fb.setupGlyphOrder(glyph_order)
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
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    # 显式重算 glyf 存储 bbox（含控制点包围盒，TrueType 规范行为）：
    # TTGlyphPen 产物边界缓存缺失，FontBuilder 保存也不补算。
    # 注意该包围盒含控制点、可大于视觉墨迹——下游视觉居中勿以此为据。
    glyf_tbl = fb.font["glyf"]
    for g in glyphs.values():
        g.recalcBounds(glyf_tbl)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1900, descent=-450)
    fb.setupNameTable({"familyName": fam_en, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=1900, sTypoDescender=-450, usWinAscent=1900, usWinDescent=450)
    fb.setupPost()
    fb.font["name"].setName(fam_zh, 1, 3, 1, 0x804)
    fb.font["name"].setName(fam_zh, 4, 3, 1, 0x804)
    fb.font["name"].setName("字形提取自 Unicode 18.0 碼表 U3D000.pdf，僅供研究使用", 13, 3, 1, 0x409)
    fb.font["OS/2"].fsType = 0
    out_ttf = ROOT / f"shuowen-seal-{tag}.ttf"
    fb.save(out_ttf)
    print(f"  {out_ttf.name}: {len(glyphs)} 字形, cmap {len(cmap)} 條 (scale={scale:.1f})", file=sys.stderr)

    # OTF：T2CharStringPen 原生三次（僅用成功字形）
    cs = {".notdef": T2CharStringPen(UPEM, None).getCharString()}
    metrics2 = {".notdef": metrics[".notdef"]}
    for d, gname in uniq.items():
        if gname not in glyphs:
            continue
        t2 = T2CharStringPen(UPEM, None)
        SvgToPen(t2, scale).draw(d)
        cs[gname] = t2.getCharString()
        metrics2[gname] = metrics[gname]
    fb2 = FontBuilder(UPEM, isTTF=False)
    fb2.setupGlyphOrder(glyph_order)
    fb2.setupCharacterMap(cmap)
    fb2.setupCFF(f"ShuowenSeal{tag}-Regular", {"FullName": fam_en}, cs, {})
    fb2.setupHorizontalMetrics(metrics2)
    fb2.setupHorizontalHeader(ascent=1900, descent=-450)
    fb2.setupNameTable({"familyName": fam_en, "styleName": "Regular"})
    fb2.setupOS2(sTypoAscender=1900, sTypoDescender=-450, usWinAscent=1900, usWinDescent=450)
    fb2.setupPost()
    fb2.font["name"].setName(fam_zh, 1, 3, 1, 0x804)
    fb2.font["name"].setName(fam_zh, 4, 3, 1, 0x804)
    fb2.font["OS/2"].fsType = 0
    out_otf = ROOT / f"shuowen-seal-{tag}.otf"
    fb2.save(out_otf)
    print(f"  {out_otf.name} 完成", file=sys.stderr)


def main():
    import glob
    files = sorted(glob.glob(str(OUTDIR / "paths_*.json")))
    assert files, "缺少 paths json"
    all_paths = defaultdict(dict)
    for fn in files:
        d = json.loads(Path(fn).read_text())
        for fam, m in d.items():
            all_paths[fam].update(m)

    import sqlite3
    con = sqlite3.connect(DB)
    mcjk_of = dict(con.execute("SELECT seal_cp, mcjk_char FROM seal_char WHERE mcjk_char IS NOT NULL"))

    # 通行字層：完整查詢鏈（依賴旁邊 zhuan/ 查表庫；不可用時降級只出前兩層）
    try:
        sys.path.insert(0, str(ROOT.parent / "zhuan"))
        from zhuan import ZhuanConverter
        cv = ZhuanConverter()
        modern = {}
        for code in range(0x3400, 0xA000):
            ch = chr(code)
            m = cv.lookup(ch)
            if m is not None:
                modern[code] = m.seal_cp
        print(f"通行字層 {len(modern)}", file=sys.stderr)
    except ImportError:
        print("警告：找不到 zhuan 查表鏈，跳過通行字層"
              "（第三層 cmap 需要旁邊有 zhuan/ 目錄，或 pip 安裝 zhuan 包）",
              file=sys.stderr)
        modern = {}

    for fam, info in FAMS.items():
        build_family(fam, info, all_paths.get(fam, {}), mcjk_of, modern)


if __name__ == "__main__":
    main()
