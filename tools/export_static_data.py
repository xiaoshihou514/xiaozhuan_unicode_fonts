#!/usr/bin/env python3
"""从 zhuan/seal.db 重导 fonts/data/ 静态映射表（需在 zhuan 环境运行）。

用法：cd ../zhuan && .venv/bin/python ../fonts/tools/export_static_data.py
产出（写入 fonts/data/）：
  - seal_sources.tsv   seal_cp, mcjk_cp, thx, ccz, qjz, dyc（编号反查＋隸定字）
  - modern_map.tsv     code, seal_cp（通行字→小篆码位，查表链产物）
  - sw_pos.tsv         head, seal_cp（說文字头对位；第二层重码裁定依据）
  - 隸定重码清单.tsv   同一隸定字对应多个码位的字与码位（第二层裁定输入）
"""
import csv
import sys
from pathlib import Path

FONTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FONTS.parent / "zhuan"))

import zhuan  # noqa: E402

DATA = FONTS / "data"


def main() -> int:
    con = zhuan.ZhuanConverter().con

    with open(DATA / "seal_sources.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["seal_cp", "mcjk_cp", "thx", "ccz", "qjz", "dyc"])
        n = 0
        for row in con.execute(
                "SELECT seal_cp, mcjk_cp, thx, ccz, qjz, dyc FROM seal_char"):
            w.writerow([row[0], row[1] or "", row[2] or "", row[3] or "",
                        row[4] or "", row[5] or ""])
            n += 1
    print(f"seal_sources.tsv: {n} 行")

    cv = zhuan.ZhuanConverter()
    with open(DATA / "modern_map.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["code", "seal_cp"])
        n = 0
        for code in range(0x3400, 0xA000):
            m = cv.lookup(chr(code))
            if m is not None:
                w.writerow([code, m.seal_cp])
                n += 1
    print(f"modern_map.tsv: {n} 行")

    with open(DATA / "sw_pos.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["head", "seal_cp"])
        n = 0
        for head, cp in con.execute("SELECT head, seal_cp FROM sw_pos"):
            w.writerow([head, cp])
            n += 1
    print(f"sw_pos.tsv: {n} 行")

    # 隸定重码清单：同一 mcjk 对应多个码位
    groups: dict[str, list[int]] = {}
    for cp, mcjk in con.execute(
            "SELECT seal_cp, mcjk_char FROM seal_char WHERE mcjk_char IS NOT NULL"):
        groups.setdefault(mcjk, []).append(cp)
    with open(DATA / "隸定重码清单.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["mcjk", "seal_cps", "sw_pos_cp", "裁定"])
        n = 0
        for mcjk, cps in sorted(groups.items()):
            if len(cps) < 2:
                continue
            w.writerow([mcjk, ",".join(str(c) for c in sorted(cps)),
                        cv._sw_pos.get(mcjk, ""), ""])
            n += 1
    print(f"隸定重码清单.tsv: {n} 个重码字")
    return 0


if __name__ == "__main__":
    sys.exit(main())
