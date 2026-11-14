"""命令行入口：xiaozhuan-fonts [all|extract|build|check] [参数...]

  all（默认）  extract → build → check 全流程
  extract [页]  码表 PDF → build_svg/paths_all.json（可指定页号或 a-b 区间调试）
  build         paths json → dist/ 四款中文名 OTF
  check [...]   交付门禁（参数同 check 模块，默认检验 dist/ 下四款）
"""
import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd, rest = (argv[0], argv[1:]) if argv else ("all", [])
    from . import build, check, extract
    if cmd == "extract":
        extract.main(rest)
    elif cmd == "build":
        build.main()
    elif cmd == "check":
        return check.main(rest)
    elif cmd == "all":
        extract.main([])
        build.main()
        return check.main([])
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0
