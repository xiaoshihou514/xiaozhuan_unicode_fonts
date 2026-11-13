#!/usr/bin/env python3
"""從 U3D000.pdf 內嵌篆體構建四款可安裝字體（一形/二形/三形/四形）。

內嵌字體為 CID TrueType（無 cmap），CID=GID。映射來源用頁面幾何而非
ToUnicode（後者對擴展區隸定字不可靠）：pymupdf texttrace 給出每個繪製
字形的 (字體, GID, 位置)，與 glyph_index 的碼位格位置（四列錨點）匹配，
得到 碼位→GID。

每款字體三層 cmap（format 12）：
  1. 小篆區 U+3D000–3FC3F → 本列篆形
  2. 隸定字漢字碼位 → 同一篆形（seal_char 的 mcjk）
  3. 通行字 → seal.db 對位（sw_pos/aliases）的篆形
用法：uv run python build_fonts.py（字形追蹤約 5 分鐘，結果有緩存）
產出 TTF 與 OTF 兩式（OTF 為 CFF 輪廓，TrueType 二次曲線經 cu2qu 轉三次）。
"""
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

ROOT = Path(__file__).parent           # legacy/
sys.path.insert(0, str(ROOT.parent))   # fonts/（fontpaths）
from fontpaths import find_pdf, find_seal_db
PDF = find_pdf()
DB = find_seal_db()
CACHE = ROOT.parent / "fonts_ext/trace.json"

SLOT_FONT = {0: "Shuowen-ccz", 1: "qjz", 2: "dyc", 3: "CMEXShuowenSeal"}   # PDF 內字體名
SLOT_FILE = {0: "Shuowen-ccz", 1: "qjz", 2: "dyc1", 3: "CMEXShuowenSeal"}  # 提取文件名
SLOT_TAG = {0: "CCZ", 1: "QJZ", 2: "DYC", 3: "THX"}                        # 來源縮寫
SLOT_ZH = {0: "陈昌治本", 1: "徐锴本", 2: "段玉裁本", 3: "藤花树本"}         # 家族中文名
SLOT_DX = {0: 65.3, 1: 90.3, 2: 119.3, 3: 35.9}
SLOT_DY = {0: -4.3, 1: 2.6, 2: 0.2, 3: 1.3}   # 錨點 top 相對標籤 top（pt）


def collect_traces(pages=None):
    """全部頁面的篆體字形追蹤：{page: {font: [(gid, x, y)]}}。"""
    doc = pymupdf.open(PDF)
    traces = {}
    pnos = pages if pages else range(1, len(doc))
    for pno in pnos:
        page = doc[pno]
        for sp in page.get_texttrace():
            f = sp["font"]
            if f not in SLOT_FONT.values():
                continue
            for uni, gid, origin, bbox in sp["chars"]:
                traces.setdefault(pno, {}).setdefault(f, []).append(
                    (gid, bbox[0], bbox[1]))
        if pno % 40 == 0:
            print(f"  texttrace 頁 {pno}", file=sys.stderr)
    doc.close()
    return traces


def ttf_to_otf(src_path: Path) -> Path:
    """TrueType 輪廓 → CFF：二次貝塞爾經 cu2qu 轉三次，輸出 OTF。"""
    from fontTools.cffLib import (CFFFontSet, CharStrings, GlobalSubrsIndex,
                                  PrivateDict, TopDict, TopDictIndex)
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.ttLib import TTFont, newTable

    MAX_ERR = 1.0   # 千分之一 em 的轉換容差
    font = TTFont(str(src_path), recalcBBoxes=False)
    glyph_order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()

    charstrings = {}
    for name in glyph_order:
        glyph = glyph_set[name]
        pen = T2CharStringPen(glyph.width, None)
        cu2qu = Cu2QuPen(pen, MAX_ERR, reverse_direction=True)
        try:
            glyph.draw(cu2qu)
        except Exception:
            pen = T2CharStringPen(glyph.width, None)   # 空字形兜底
        charstrings[name] = pen.getCharString()

    private = PrivateDict()
    private.rawDict.update({
        "defaultWidthX": round(sum(g.width for g in glyph_set.values()) / len(glyph_order)),
        "NominalWidthX": 0,
    })
    top = TopDict()
    top.Private = private
    top.charset = glyph_order
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]    # upem 1000 標準矩陣
    cs = CharStrings(None, None, None, private, None, None)
    cs.charStrings = charstrings                   # 插入序即字形序（.notdef 首）
    top.CharStrings = cs
    font_names = [r.toUnicode() for r in font["name"].names if r.nameID == 6]
    cff = newTable("CFF ")
    cff.cff = CFFFontSet()
    cff.cff.major, cff.cff.minor = 1, 0
    cff.cff.fontNames = [font_names[0] if font_names else "SealFont"]
    cff.cff.GlobalSubrs = GlobalSubrsIndex()
    cff.cff.topDictIndex = TopDictIndex()
    cff.cff.topDictIndex.append(top)
    font["CFF "] = cff

    for tag in ("glyf", "loca", "cvt ", "fpgm", "prep", "gasp"):
        if tag in font:
            del font[tag]
    font.sfntVersion = "OTTO"
    maxp = font["maxp"]
    maxp.tableVersion = 0x00005000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs",
                 "maxInstructionDefs", "maxStackElements", "maxSizeOfInstructions",
                 "maxComponentElements"):
        if hasattr(maxp, attr):
            setattr(maxp, attr, 0)
    maxp.numGlyphs = len(glyph_order)
    out = src_path.with_suffix(".otf")
    font.save(out)
    font.close()
    return out


def main():
    sys.path.insert(0, str(ROOT.parent.parent / "zhuan"))
    from zhuan.glyph import build_index
    idx = build_index()

    if CACHE.exists():
        traces = {int(k): v for k, v in json.loads(CACHE.read_text()).items()}
        print(f"字形追蹤緩存：{sum(len(v) for p in traces.values() for v in p.values())} 字形", file=sys.stderr)
    else:
        print("texttrace 全頁掃描…（約 5 分鐘）", file=sys.stderr)
        traces = collect_traces()
        CACHE.write_text(json.dumps(traces))
        print("掃描完成，已緩存", file=sys.stderr)

    # 每個碼位 → 各列 GID
    cp_gids = {s: {} for s in SLOT_FONT}   # slot -> {cp: gid}
    missing = 0
    for cp, (pno, lx, lt) in idx.items():
        page_tr = traces.get(pno, {})
        for slot, fname in SLOT_FONT.items():
            want_x = lx + SLOT_DX[slot]
            want_y = lt + SLOT_DY[slot]
            best, bd = None, 1e9
            for gid, x, y in page_tr.get(fname, ()):
                d = abs(x - want_x) + abs(y - want_y) * 0.5
                if d < bd and abs(x - want_x) <= 6 and abs(y - want_y) <= 12:
                    best, bd = gid, d
            if best is not None:
                cp_gids[slot][cp] = best
            else:
                missing += 1
    print(f"碼位配對：一形 {len(cp_gids[0])} 二形 {len(cp_gids[1])} "
          f"三形 {len(cp_gids[2])} 四形 {len(cp_gids[3])}（缺 {missing}）", file=sys.stderr)

    con = sqlite3.connect(DB)
    mcjk_of = dict(con.execute("SELECT seal_cp, mcjk_char FROM seal_char WHERE mcjk_char IS NOT NULL"))

    for slot, fname in SLOT_FONT.items():
        src = TTFont(ROOT / f"fonts_ext/{SLOT_FILE[slot]}.ttf")
        gname = src.getGlyphName
        mapping = {}
        for cp, gid in cp_gids[slot].items():
            if gid < src["maxp"].numGlyphs:
                mapping[cp] = gname(gid)
                mc = mcjk_of.get(cp)
                if mc:
                    mapping.setdefault(ord(mc), gname(gid))     # 隸定字層
        # 通行字層：跑完整查詢鏈（OpenCC/BFS/借聲符），覆蓋=轉換器
        from zhuan import ZhuanConverter
        cv = ZhuanConverter()
        n_modern = 0
        for code in range(0x3400, 0xA000):        # CJK 基本區＋擴展A
            ch = chr(code)
            if code in mapping:
                continue
            m = cv.lookup(ch)
            if m is None:
                continue
            gid = cp_gids[slot].get(m.seal_cp)
            if gid is not None and gid < src["maxp"].numGlyphs:
                mapping[code] = gname(gid)
                n_modern += 1
        print(f"  通行字層 {n_modern}", file=sys.stderr)

        cmap_table = newTable("cmap")
        cmap_table.tableVersion = 0
        sub = CmapSubtable.getSubtableClass(12)()
        sub.platformID, sub.platEncID, sub.format, sub.language = 3, 10, 12, 0
        sub.cmap = dict(sorted(mapping.items()))
        cmap_table.tables = [sub]
        src["cmap"] = cmap_table
        if not mapping:
            print(f"  跳过空映射 slot {slot}", file=sys.stderr)
            continue
        # name 表整表重建——原嵌入字體的名錄（HOCLEF+ 前綴等）全數丟棄。
        # 家族名中英各錄一份（英文保底，中文供系統字體選單顯示）
        name = newTable("name")
        name.names = []
        for lang, fam in [(0x409, f"Shuowen Seal {SLOT_TAG[slot]}"),
                          (0x804, f"说文小篆-{SLOT_ZH[slot]}")]:
            # setName(串, 名ID, 平台3=Win, 编码1=UCS-2, 语言ID)
            name.setName(fam, 1, 3, 1, lang)
            name.setName("Regular", 2, 3, 1, lang)
            name.setName(fam, 4, 3, 1, lang)
            name.setName(f"ShuowenSeal{SLOT_TAG[slot]}-Regular", 6, 3, 1, lang)
            name.setName("字形提取自 Unicode 18.0 碼表 U3D000.pdf，僅供研究使用",
                         13, 3, 1, lang)
        src["name"] = name
        src["OS/2"].fsType = 0
        out = ROOT / f"shuowen-seal-{SLOT_TAG[slot]}.ttf"
        src.save(out)
        print(f"  {out.name}: cmap {len(mapping)} 條", file=sys.stderr)
        src.close()
        otf = ttf_to_otf(out)
        print(f"  {otf.name}: {otf.stat().st_size // 1024 // 1024}MB "
              f"(TTF {out.stat().st_size // 1024 // 1024}MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
