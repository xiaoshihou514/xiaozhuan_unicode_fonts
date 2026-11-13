#!/usr/bin/env python3
"""居中回归检测入口（task-36 审计后改版）。

居中检查已并入独立门禁 check_fonts.py（Q3 绝对标准：墨迹中心距字面
中线 0.38em ≤2% em、墨迹在 [−0.10,+0.86] 字面区内、宽高比贴合 96%/98%
目标）。本脚本保留为兼容入口，直接委托，避免「用构建规则自验自己」。
"""
import sys

import check_fonts

if __name__ == "__main__":
    sys.exit(check_fonts.main())
