# 說文小篆字体管线一键复现
# 安装 just：https://github.com/casey/just#packages （或 cargo install just / pipx install rust-just）

# 一键全流程：SVG 提取（有 paths 缓存则秒级）→ 构建四款中文名 OTF
otf:
    uv run build_fonts_svg.py
    uv run build_ttf_from_paths.py

# 居中回归检测（偏差 >2% em 即失败）
check:
    uv run check_centering.py

# 全流程＋把关
all: otf check

# 清理构建产物（OTF 会重新生成，请先确认无需保留）
clean:
    rm -rf build_svg *.otf
