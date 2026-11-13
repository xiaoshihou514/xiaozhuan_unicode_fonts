#!/usr/bin/env python3
"""发布后复验（v0.1.3）：覆盖、映射语义、元数据。只读。

用法（fonts/ 下）：uv run --offline python audit/工具/复验/复验映射.py audit/_release-v0.1.3
输出：audit/数据/复验/映射逐条.tsv 及标准输出摘要。
"""
import csv
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(FONTS))
from fontpaths import load_seal_sources   # noqa: E402

REL = {"ccz": "ShuowenSeal-ChenChangzhi.otf", "qjz": "ShuowenSeal-XuKai.otf",
       "dyc": "ShuowenSeal-DuanYucai.otf", "thx": "ShuowenSeal-TengHuaShu.otf"}
ZH = {"ccz": "陈昌治本", "qjz": "徐锴本", "dyc": "段玉裁本", "thx": "藤花树本"}
OLD = FONTS / "audit" / "_release"


def cp_of(glyph):
    return int(glyph[1:], 16) if glyph and glyph.startswith("u") else None


def main():
    fdir = FONTS / sys.argv[1]
    out = FONTS / "audit" / "数据" / "复验"
    out.mkdir(parents=True, exist_ok=True)
    fam_map, mcjk_of = load_seal_sources()
    new = {f: TTFont(str(fdir / r)) for f, r in REL.items()}
    old = {f: TTFont(str(OLD / r)) for f, r in REL.items()}
    ncm = {f: t.getBestCmap() for f, t in new.items()}
    ocm = {f: t.getBestCmap() for f, t in old.items()}
    lines = []

    # 1) 覆盖：映射表编号 → 字体篆区码位
    miss_prev = [l.rstrip("\n").split("\t") for l in
                 open(FONTS / "audit" / "数据" / "漏提诊断.tsv", encoding="utf-8")][1:]
    print("== 覆盖（G3/G4）")
    for f in REL:
        want = set(fam_map[f].values())
        got = {c for c in ncm[f] if 0x3D000 <= c <= 0x3FC3F}
        print(f"  {ZH[f]}: 应有 {len(want)} 实有 {len(got & want)} 缺 {len(want - got)} 多 {len(got - want)}")
    back = sum(1 for r in miss_prev if int(r[2][2:], 16) in ncm[r[0]])
    print(f"  首轮 837 条漏提：v0.1.3 已有字形 {back}/{len(miss_prev)}")
    for r in miss_prev:
        if int(r[2][2:], 16) not in ncm[r[0]]:
            lines.append(f"漏提未回收\t{r[0]}\t{r[2]}\t{r[1]}")

    # 2) 空字形与 .notdef
    print("== 空字形（Q1）/ .notdef（G7）")
    for f, t in new.items():
        gs = t.getGlyphSet()
        empty = 0
        seen = {}
        for c, g in ncm[f].items():
            if g not in seen:
                b = BoundsPen(gs); gs[g].draw(b); seen[g] = b.bounds is None
            empty += seen[g]
        b = BoundsPen(gs); gs[".notdef"].draw(b)
        print(f"  {ZH[f]}: cmap {len(ncm[f])} 空 {empty}；.notdef 包围盒 {b.bounds}")

    # 3) 精筛 107 条逐条
    print("== G1 精筛 107 条")
    rows = [l.rstrip("\n").split("\t") for l in
            open(FONTS / "audit" / "数据" / "通行字错映-精筛.tsv", encoding="utf-8")][1:]
    wl = {r["char"]: int(r["actual_cp"], 16) for r in
          csv.DictReader(open(FONTS / "data" / "映射白名单.tsv", encoding="utf-8"), delimiter="\t")}
    stat = {}
    for ch, oldcp, oldmc, headcp, headmc in rows:
        oldcp, headcp = int(oldcp[2:], 16), int(headcp[2:], 16)
        per = []
        for f in REL:
            g = ncm[f].get(ord(ch))
            per.append(cp_of(g))
        vals = {v for v in per if v is not None}
        if not vals:
            st = "四款均无映射"
        elif vals == {headcp}:
            st = "改为字头位"
        elif oldcp in vals:
            st = "白名单维持" if ch in wl else "仍为旧错映"
        else:
            st = "改为其他码位"
        stat[st] = stat.get(st, 0) + 1
        newdesc = ",".join("—" if v is None else f"U+{v:X}({mcjk_of.get(v, '')})" for v in per)
        lines.append(f"精筛\t{ch}\t{st}\t旧 U+{oldcp:X}({oldmc})\t字头 U+{headcp:X}({headmc})\t新[ccz,qjz,dyc,thx] {newdesc}")
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # 4) G10 隸定层 33 条
    print("== G10 隸定层重码 33 条")
    g10 = [l.rstrip("\n").split("\t") for l in
           open(FONTS / "audit" / "数据" / "映射审计.tsv", encoding="utf-8") if l.startswith("隸定层错映")]
    st10 = {}
    for _, ch, _, l2, head in g10:
        l2c, hc = int(l2.split("U+")[1], 16), int(head.split("U+")[1], 16)
        vals = {cp_of(ncm[f].get(ord(ch))) for f in REL} - {None}
        s = "改为字头位" if vals == {hc} else ("仍为旧码位" if l2c in vals else f"其他{sorted(hex(v) for v in vals)}")
        st10[s] = st10.get(s, 0) + 1
        lines.append(f"G10\t{ch}\t{s}\t旧 U+{l2c:X}\t字头 U+{hc:X}")
    for k, v in st10.items():
        print(f"  {k}: {v}")

    # 5) 特裁字与黄金表
    print("== 特裁字")
    spec = [("二", 0x3F850), ("光", 0x3ED49), ("煙", 0x3ED2C), ("關", 0x3F2CA), ("親", 0x3E8DB),
            ("詳", 0x3D6B6), ("壹", 0x3EDE2), ("面", 0x3E9A7), ("白", 0x3E657), ("舌", 0x3D429),
            ("滚", None), ("他", 0x3F834), ("她", 0x3F834), ("上", 0x3D008), ("一", 0x3D000)]
    for ch, exp in spec:
        got = [cp_of(ncm[f].get(ord(ch))) for f in REL]
        desc = " ".join(f"{ZH[f][:2]}:{'—' if v is None else f'U+{v:X}'}" for f, v in zip(REL, got))
        print(f"  {ch} 期望 {'无映射（回退）' if exp is None else f'U+{exp:X}'}：{desc}")
    gold = list(csv.DictReader(open(FONTS / "data" / "黄金映射.tsv", encoding="utf-8"), delimiter="\t"))
    bad = []
    for r in gold:
        exp = int(r["expect_cp"], 16)
        for f in REL:
            v = cp_of(ncm[f].get(ord(r["char"])))
            if v is not None and v != exp:
                bad.append((r["char"], f, v))
    print(f"  黄金映射表 {len(gold)} 条：与字体不符 {len(bad)} {bad[:5]}")

    # 6) GB2312 一级覆盖
    l1 = []
    for b1 in range(0xB0, 0xD8):
        for b2 in range(0xA1, 0xFF):
            try:
                l1.append(ord(bytes([b1, b2]).decode("gb2312")))
            except Exception:
                pass
    print("== GB2312 一级字覆盖（v0.1.1 → v0.1.3）")
    for f in REL:
        print(f"  {ZH[f]}: {sum(c in ocm[f] for c in l1)} → {sum(c in ncm[f] for c in l1)}")
    lost = {f: [chr(c) for c in l1 if c in ocm[f] and c not in ncm[f]] for f in REL}
    for f, v in lost.items():
        if v:
            print(f"  {ZH[f]} 相对 v0.1.1 失去：{len(v)} 字 {''.join(v[:40])}")
            lines.append(f"覆盖回退\t{f}\t{''.join(v)}")

    # 7) 元数据
    print("== 元数据（G8）")
    for f, t in new.items():
        nm = t["name"]
        o = t["OS/2"]
        hh = t["hhea"]
        print(f"  {ZH[f]}: ID5={nm.getDebugName(5)!r} head.rev={t['head'].fontRevision:.3f} "
              f"typo={o.sTypoAscender}/{o.sTypoDescender}/{o.sTypoLineGap} win={o.usWinAscent}/{o.usWinDescent} "
              f"hhea={hh.ascent}/{hh.descent} fsSel={o.fsSelection:#x} cp1={o.ulCodePageRange1:#x} "
              f"vend={o.achVendID!r} post={t['post'].formatType} vhea={'vhea' in t} VORG={'VORG' in t}")
    (out / "映射逐条.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"明细 → audit/数据/复验/映射逐条.tsv（{len(lines)} 行）")


if __name__ == "__main__":
    main()
