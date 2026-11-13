# 說文小篆字体管线一键复现
# 安装 just：https://github.com/casey/just#packages

# 全流程＋门禁（任何一项失败即非零退出）
otf:
    uv run build_fonts_svg.py
    uv run build_ttf_from_paths.py
    uv run check_fonts.py --version {{version}}

# 独立门禁（可单独运行）
check:
    uv run check_fonts.py --version {{version}}

release: otf
    #!/bin/sh
    git diff --quiet && git diff --cached --quiet || { echo "工作区不干净（Q10）"; exit 1; }
    shasum -a 256 说文小篆-*.otf > sha256sums.txt || sha256sum 说文小篆-*.otf > sha256sums.txt
    echo "已输出 sha256sums.txt（上传 Release 后回下载比对）"

# 清理构建产物
clean:
    rm -rf build_svg *.otf .build-*.ttf .norm-*.ttf

version := "0.1.2"
