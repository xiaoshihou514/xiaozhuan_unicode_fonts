#!/usr/bin/env python3
"""從 build_fonts_svg.py 產出的矢量 path 構建四款說文小篆字體（交付用中文名 OTF）。

R1 單階段管線（審計 task-36 建議）：
  源路徑精確包圍盒（先剔碎屑）→ 一次仿射（無條件字面居中）→ 取整一次
  → pathops 疊加化（三次曲線直上）→ 直寫 T2CharStringPen（CFF）。
  不回讀已構建的字形（規避 glyf 未編譯對象錯位陷阱），無二次量化，
  無 TrueType 繞道。

靜態映射表（data/）供第二、三層 cmap；分款回退表處理官方數據缺口。
"""
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pathops
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen

ROOT = Path(__file__).parent
OUTDIR = ROOT / "build_svg"
from fontpaths import load_seal_sources, load_modern_map, load_sw_pos   # noqa: E402

UPEM = 2048

# 度量歸一常量（視覺定位以精確墨跡輪廓為準；存儲 bbox 含控制點不可作依據）
INK_H = 0.96   # 目標墨跡高度 / em
INK_W = 0.98   # 目標墨跡寬度上限 / em
TOP = 0.86     # 字面區頂 / em
BOT = -0.10    # 字面區底 / em
ZONE_MID = (TOP + BOT) / 2          # 字面垂直中心（S3：無條件居中）
DEBRIS_AREA = 0.0002 * UPEM * UPEM  # 碎屑面積閾值（M4/G6：0.02% em²）

VERSION = os.environ.get("FONT_VERSION", "0.1.2")

FAMS = {
    "thx": dict(tag="THX", zh="藤花树本"),
    "ccz": dict(tag="CCZ", zh="陈昌治本"),
    "qjz": dict(tag="QJZ", zh="徐锴本"),
    "dyc": dict(tag="DYC", zh="段玉裁本"),
}

# SVG path（y 向下、基線 0）→ fontTools pen（y 向上）
class SvgToPen:
    """把 pdftocairo path d 畫到 pen，y 翻轉 + 縮放。"""

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


def contours_of(d, scale):
    """把 path d 拆成單個輪廓的 RecordingPen 值（y 翻轉縮放後）。"""
    rp = RecordingPen(d, scale)
    contours = []
    cur = []
    for op, args in rp.value:
        if op == "moveTo":
            if cur:
                contours.append(cur)
            cur = [(op, args)]
        else:
            cur.append((op, args))
    if cur:
        contours.append(cur)
    return contours


class RecordingPen:
    """記錄 SvgToPen 輸出（含 curveTo 三次）。"""

    def __init__(self, d, scale):
        self.value = []
        SvgToPen(self, scale).draw(d)

    def moveTo(self, pt):
        self.value.append(("moveTo", (pt,)))

    def lineTo(self, pt):
        self.value.append(("lineTo", (pt,)))

    def curveTo(self, *pts):
        self.value.append(("curveTo", tuple(pts)))

    def closePath(self):
        self.value.append(("closePath", ()))

    def closeContour(self):
        self.value.append(("closePath", ()))


def contour_area(ops):
    """鞋帶公式近似有向面積（曲線取採樣點；用於碎屑判定足夠）。"""
    pts = []
    for op, args in ops:
        if op == "moveTo":
            pts.append(args[0])
        elif op in ("lineTo", "curveTo"):
            pts.extend(args if op == "lineTo" else [args[-1]])
        elif op == "closePath":
            pass
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


def draw_ops(ops, pen):
    for op, args in ops:
        getattr(pen, op)(*args)


def build_family(fam, info, paths, mcjk_groups, sw_pos, modern, fallbacks):
    tag, zh = info["tag"], info["zh"]
    cps = sorted(int(cp) for cp in paths)

    # 縮放基準：字形主高約 0.75em
    heights = []
    for d in list(paths.values())[:400]:
        ys = [float(n) for n in __import__("re").findall(r"-?[\d.]+", d)][1::2]
        if ys:
            heights.append(max(ys) - min(ys))
    h_med = statistics_median(heights)
    scale = UPEM * 0.75 / h_med

    uniq = {}
    cp_glyph = {}
    for cp in cps:
        d = paths[str(cp)]
        if d not in uniq:
            uniq[d] = f"u{cp:X}"
        cp_glyph[cp] = uniq[d]

    glyph_order = [".notdef"]
    simplified = {}      # gname -> pathops.Path（疊加化後，浮點）
    metrics = {}
    cmap_glyph = {}
    bad = 0
    for d, gname in uniq.items():
        try:
            contours = contours_of(d, scale)
            if not contours:
                raise ValueError("空輪廓")
            # 碎屑剔除（M4/G6）：源路徑 y 翻轉後外輪廓為負方向——
            # 「負且面積小於閾值」即游離黑碎屑，刪除；小的正面積輪廓
            # 是設計鏤空白孔，保留（v0.1.3 曾把條件寫反，誤刪 3,380 個白孔）
            kept = [c for c in contours
                    if not (contour_area(c) < 0
                            and abs(contour_area(c)) < DEBRIS_AREA)]
            if not kept:
                kept = contours
            # 精確墨跡包圍盒（剔碎屑後）
            rp = _ReplayPen(kept)
            bp = BoundsPen(None)
            rp.replay(bp)
            if not bp.bounds:
                raise ValueError("空包圍盒")
            x0, y0, x1, y1 = bp.bounds
            w, h = x1 - x0, y1 - y0
            # 一次仿射：全角水平居中 + 無條件字面垂直居中（S3）
            s2 = min(INK_H * UPEM / h, INK_W * UPEM / w)
            tx = 0.5 * UPEM - w * s2 / 2 - x0 * s2
            ty = ZONE_MID * UPEM - (y0 + y1) / 2 * s2
            # pathops 輸入：一次仿射後取整一次（全程唯一量化）。
            # 浮點自交路徑直接 simplify 會觸發 skia 丟區域缺陷
            # （實證：0x3FBB3/0x3DB8F 等字上半部丟失），取整後正確。
            sk = pathops.Path()
            tp = TransformPen(_RoundPen(sk.getPen()), (s2, 0, 0, s2, tx, ty))
            _ReplayPen(kept).replay(tp)
            r = sk.simplify()
            simplified[gname] = sk if r is None else r
            glyph_order.append(gname)
            lsb = int(round(x0 * s2 + tx))
            metrics[gname] = (UPEM, lsb)
        except Exception as e:
            bad += 1
            if bad <= 3:
                print(f"  跳過壞字形 {gname}: {e}", file=sys.stderr)
    if bad:
        # M6：壞字形靜默缺失不可接受
        sys.exit(f"{fam_zh}: {bad} 個字形構建失敗，拒絕交付")
    # .notdef：空心方框（G7/S6：缺字可見而非空白）
    nd = pathops.Path()
    npen = nd.getPen()
    m = int(0.05 * UPEM)
    npen.moveTo((m, -m))
    npen.lineTo((UPEM - m, -m))
    npen.lineTo((UPEM - m, UPEM - m))
    npen.lineTo((m, UPEM - m))
    npen.closePath()
    inner = int(0.12 * UPEM)
    npen.moveTo((inner, inner))
    npen.lineTo((inner, UPEM - inner))
    npen.lineTo((UPEM - inner, UPEM - inner))
    npen.lineTo((UPEM - inner, inner))
    npen.closePath()
    _r = nd.simplify()
    simplified[".notdef"] = nd if _r is None else _r
    metrics[".notdef"] = (UPEM, 0)
    cmap_glyph = {cp: g for cp, g in cp_glyph.items() if g in simplified}
    print(f"  疊加化＋取整完成（{len(simplified)} 字形）", file=sys.stderr)

    # 三層 cmap
    cmap = {}
    for cp, g in cmap_glyph.items():
        cmap[cp] = g
    # 第二層（隸定字）：重碼時優先取《說文》字頭碼位（G10），否則最小碼位；
    # 無法裁定的已記錄於 data/隸定重码清单.tsv 待人工確認
    for mcjk, cps_shared in sorted(mcjk_groups.items()):
        cps_avail = sorted(c for c in cps_shared if c in cmap_glyph)
        if not cps_avail:
            continue
        g = cmap_glyph[cps_avail[0]]
        if mcjk in sw_pos and sw_pos[mcjk] in cmap_glyph:
            g = cmap_glyph[sw_pos[mcjk]]
        cmap.setdefault(ord(mcjk), g)
    # 第三層（通行字）＋分款回退（Q6：官方數據缺口顯式聲明）
    for code, cp in modern.items():
        g = cmap_glyph.get(cp)
        if g:
            cmap.setdefault(code, g)
    for code, cp in fallbacks.get(fam, {}).items():
        g = cmap_glyph.get(cp)
        if g:
            cmap[code] = g   # 回退是顯式覆蓋
        else:
            print(f"  [回退] {fam} U+{code:X} → U+{cp:X} 本款無字形，未應用",
                  file=sys.stderr)

    fam_en = f"Shuowen Seal {tag}"
    fam_zh = f"说文小篆-{zh}"
    ps = f"ShuowenSeal{tag}-Regular"

    # 直寫 CFF：疊加化路徑取整一次送 T2CharStringPen
    # （pathops 輸出可能含二次曲線，統一轉三次；無量化損失）
    from fontTools.pens.qu2cuPen import Qu2CuPen
    cs = {}
    for name in glyph_order:
        t2 = T2CharStringPen(UPEM, None)
        rpen = _RoundPen(t2)
        q2c = Qu2CuPen(rpen, max_err=1.0, all_cubic=True)
        simplified[name].draw(q2c)
        cs[name] = t2.getCharString()

    # 版本元數據（Q9/Q10）：SOURCE_DATE_EPOCH 可復現
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    version_s = f"Version {VERSION}"

    fb = FontBuilder(UPEM, isTTF=False)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupCFF(ps, {"FullName": fam_en}, cs, {})
    fb.setupHorizontalMetrics(metrics)
    # M7/G8：行框 ≥1em（0.88/−0.12），usWin 留 2 單位餘量，不截斷
    asc = round(0.88 * UPEM)
    desc = round(-0.12 * UPEM)
    fb.setupHorizontalHeader(ascent=asc, descent=desc)
    fb.setupNameTable({"familyName": fam_en, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=asc, sTypoDescender=desc,
                usWinAscent=round(TOP * UPEM) + 2,
                usWinDescent=round(-BOT * UPEM) + 2)
    fb.setupPost()
    os2 = fb.font["OS/2"]
    os2.version = 4                          # USE_TYPO_METRICS 位需 v4+
    os2.fsSelection = 0x40 | 0x80          # REGULAR + USE_TYPO_METRICS
    os2.ulCodePageRange1 = 0x00060001      # Latin1 + GB2312 + Big5
    os2.achVendID = "XZSC"
    name = fb.font["name"]
    for lang in (0x409, 0x804):
        zh_fam = fam_zh if lang == 0x804 else fam_en
        name.setName(zh_fam, 1, 3, 1, lang)
        name.setName("Regular" if lang == 0x409 else "常规", 2, 3, 1, lang)
        name.setName(zh_fam, 4, 3, 1, lang)
        name.setName(ps, 6, 3, 1, lang)
        name.setName(f"{ps};{version_s}", 3, 3, 1, lang)
        name.setName(version_s, 5, 3, 1, lang)
    lic = "字形提取自 Unicode 18.0 碼表 U3D000.pdf，僅供研究使用"
    lic_en = "Glyphs from Unicode 18.0 code chart U3D000.pdf, for research only"
    name.setName(lic, 13, 3, 1, 0x804)
    name.setName(lic_en, 13, 3, 1, 0x409)
    fb.font["OS/2"].fsType = 0
    # head 版本與時間戳（Q10 可復現）
    # fontRevision 與 name 版本一致化（audit 復驗 3.3：舊寫法得 16.0）
    major, minor = VERSION.split(".")[:2]
    fb.font["head"].fontRevision = float(f"{major}.{int(minor)}")
    if epoch:
        dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        for tbl_attr in ("created", "modified"):
            setattr(fb.font["head"], tbl_attr, dt)

    # 竪排度量（G8）：全角 advanceHeight，tsb 按字面區居中
    vmtx = {}
    for gname in glyph_order:
        vmtx[gname] = (UPEM, asc - int(0.86 * UPEM))
    vhea = newTable("vhea")
    vhea.tableVersion = 0x00010000
    vhea.ascent = asc
    vhea.descent = desc
    vhea.lineGap = 0
    vhea.advanceHeightMax = UPEM
    vhea.minTopSideBearing = asc - int(0.86 * UPEM)
    vhea.minBottomSideBearing = desc
    vhea.yMaxExtent = int(0.86 * UPEM) - desc
    vhea.number_of_vmetrics = len(glyph_order)
    vhea.caretSlopeRise = 1
    vhea.caretSlopeRun = 0
    vhea.caretOffset = 0
    vhea.reserved1 = 0
    vhea.reserved2 = 0
    vhea.reserved3 = 0
    vhea.reserved4 = 0
    vhea.reserved5 = 0
    vhea.metricDataFormat = 0
    fb.font["vhea"] = vhea
    vmtx_tbl = newTable("vmtx")
    vmtx_tbl.metrics = vmtx
    fb.font["vmtx"] = vmtx_tbl
    try:
        fb.font["post"].formatType = 3.0
    except Exception:
        pass

    out = ROOT / f"{fam_zh}.otf"
    fb.save(out)
    print(f"  {out.name}: {len(glyph_order)} 字形, cmap {len(cmap)} 條", file=sys.stderr)


def statistics_median(values):
    values = sorted(values)
    n = len(values)
    if n % 2:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2


class _ReplayPen:
    """重放記錄的輪廓序列。"""

    def __init__(self, contours):
        self.contours = contours

    def replay(self, pen):
        for contour in self.contours:
            draw_ops(contour, pen)


class _RoundPen:
    """取整一次（R1：全程唯一一次量化）。"""

    def __init__(self, out):
        self.out = out
        self._last = (0, 0)

    def _r(self, p):
        return (int(round(p[0])), int(round(p[1])))

    def moveTo(self, pt):
        self._last = pt
        self.out.moveTo(self._r(pt))

    def lineTo(self, pt):
        self._last = pt
        self.out.lineTo(self._r(pt))

    def curveTo(self, *pts):
        self._last = pts[-1]
        self.out.curveTo(*[self._r(p) for p in pts])

    def closePath(self):
        self.out.closePath()

    # 注意：本筆不實現 qCurveTo——pathops.Path.draw 會按輸出筆能力
    # 切換格式，quad 輸出路徑存在丟區域問題（審計 v0.1.2 落地時實證），
    # 無 qCurveTo 時強制輸出三次曲線，保真。


def main():
    files = sorted(glob.glob(str(OUTDIR / "paths_all.json"))) or \
        sorted(glob.glob(str(OUTDIR / "paths_*.json")))
    assert files, "缺少 paths json（先運行 build_fonts_svg.py）"
    all_paths = defaultdict(dict)
    for fn in files:
        d = json.loads(Path(fn).read_text())
        for fam, m in d.items():
            all_paths[fam].update(m)

    seal_map, mcjk_single = load_seal_sources()
    modern = load_modern_map()
    sw_pos = load_sw_pos()

    # 隸定字 → 共享碼位組（G10 重碼裁定）
    mcjk_groups: dict[str, list[int]] = defaultdict(list)
    for row in load_tsv_rows("seal_sources.tsv"):
        mc = row["mcjk_cp"]
        if mc:
            mcjk_groups[chr(int(mc))].append(int(row["seal_cp"]))

    # 分款回退表（Q6）：data/分款回退.tsv —— fam, code, seal_cp, note
    fallbacks: dict[str, dict[int, int]] = defaultdict(dict)
    fb_path = ROOT / "data" / "分款回退.tsv"
    if fb_path.exists():
        for line in fb_path.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            fam, code, cp, *_note = line.split("\t")
            fallbacks[fam][int(code, 16)] = int(cp, 16)

    print(f"通行字層 {len(modern)}（data/modern_map.tsv）", file=sys.stderr)
    for fam, info in FAMS.items():
        build_family(fam, info, all_paths.get(fam, {}), mcjk_groups,
                     sw_pos, modern, fallbacks)


def load_tsv_rows(name):
    from fontpaths import load_tsv
    return load_tsv(name)


if __name__ == "__main__":
    main()
