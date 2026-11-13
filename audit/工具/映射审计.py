#!/usr/bin/env python3
"""独立审计：码位覆盖与 cmap 映射一致性（只读）。

1) 提取覆盖：seal_sources.tsv 中有该家编号的码位 vs paths json 实际提取到的码位；
2) 第三层（通行字）语义：modern_map 中「字头本身就是《說文》字头」的条目，
   其映射码位应等于 seal.db sw_pos 的字头码位（若 ../zhuan/seal.db 可读）；
3) 各款对通行字/隸定字的「缺形」：映射目标码位在该款无字形 → cmap 缺项，
   渲染器若无回退即显示 .notdef（本字体 .notdef 为空白）。
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FONTS))
from fontpaths import load_modern_map, load_seal_sources, load_tsv   # noqa: E402

REL = {"ccz": "ShuowenSeal-ChenChangzhi.otf", "qjz": "ShuowenSeal-XuKai.otf",
       "dyc": "ShuowenSeal-DuanYucai.otf", "thx": "ShuowenSeal-TengHuaShu.otf"}
ZH = {"ccz": "陈昌治本", "qjz": "徐锴本", "dyc": "段玉裁本", "thx": "藤花树本"}


def main():
    out = FONTS / "audit" / "数据"
    out.mkdir(parents=True, exist_ok=True)
    paths = json.loads((FONTS / "build_svg" / "paths_1-189.json").read_text())
    fam_map, mcjk_of = load_seal_sources()
    modern = load_modern_map()
    rows = load_tsv("seal_sources.tsv")
    print(f"seal_sources 行 {len(rows)}，不同码位 {len({r['seal_cp'] for r in rows})}")

    lines = []
    # 1) 提取覆盖
    for fam in ("ccz", "qjz", "dyc", "thx"):
        want = set(fam_map[fam].values())
        got = {int(k) for k in paths[fam]}
        miss = sorted(want - got)
        extra = sorted(got - want)
        # 去重共享（同一 path 多码位）
        dup = Counter(paths[fam].values())
        shared = sum(n for n in dup.values() if n > 1)
        print(f"[覆盖] {ZH[fam]}: 应有 {len(want)} 提取 {len(got)} 漏提 {len(miss)} "
              f"多余 {len(extra)} 同形共享码位 {shared}")
        for cp in miss:
            num = [k for k, v in fam_map[fam].items() if v == cp]
            lines.append(f"漏提\t{ZH[fam]}\tU+{cp:X}\t{','.join(num)}")

    # 2) 第三层语义
    db = FONTS.parent / "zhuan" / "seal.db"
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        head = {h: cp for h, cp in con.execute("select head, seal_cp from sw_pos")}
        bad = []
        for code, cp in modern.items():
            ch = chr(code)
            if ch in head and head[ch] != cp:
                bad.append((ch, cp, head[ch]))
        print(f"[语义] 通行字映射总数 {len(modern)}；字头本身即《說文》字头但映射到别字的 {len(bad)} 条")
        for ch, cp, h in bad:
            mc = mcjk_of.get(cp, "")
            mh = mcjk_of.get(h, "")
            lines.append(f"通行字错映\t{ch}\tU+{ord(ch):X}\t现映射 U+{cp:X}({mc})\t字头 U+{h:X}({mh})")
        # 第二层 vs 字头：隸定字（setdefault 先到先得）
        bad2 = []
        for ch, h in head.items():
            if len(ch) != 1:
                continue
            c = ord(ch)
            # 找第二层会把 c 映射到哪个码位（cmap 构建顺序：码位升序 setdefault）
            l2 = sorted(cp for cp, m in mcjk_of.items() if m == ch)
            if l2 and l2[0] != h:
                bad2.append((ch, l2[0], h))
        print(f"[语义] 隸定字层：字头字符经第二层落到非字头码位的 {len(bad2)} 条")
        for ch, cp, h in bad2:
            lines.append(f"隸定层错映\t{ch}\tU+{ord(ch):X}\t第二层 U+{cp:X}\t字头 U+{h:X}")
    else:
        print("[语义] 未找到 ../zhuan/seal.db，跳过")

    # 3) 各款缺形（以 Release 字体 cmap 为准）
    for fam in ("ccz", "qjz", "dyc", "thx"):
        ft = TTFont(str(FONTS / "audit" / "_release" / REL[fam]))
        cm = ft.getBestCmap()
        got = {int(k) for k in paths[fam]}
        miss_modern = [(c, cp) for c, cp in modern.items() if cp not in got and c not in cm]
        miss_mc = sorted({ord(m) for cp, m in mcjk_of.items()} - set(cm))
        nd = ft["glyf"] if "glyf" in ft else None
        print(f"[缺形] {ZH[fam]}: cmap {len(cm)}；通行字层目标无字形 {len(miss_modern)}；"
              f"隸定字未映射 {len(miss_mc)}")
        for c, cp in miss_modern:
            lines.append(f"通行字缺形\t{ZH[fam]}\t{chr(c)}\tU+{c:X}\t目标 U+{cp:X}")
    (out / "映射审计.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"明细 → audit/数据/映射审计.tsv（{len(lines)} 行）")


if __name__ == "__main__":
    main()
