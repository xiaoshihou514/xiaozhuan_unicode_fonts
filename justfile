# 說文小篆字体管线（版本号唯一来源：pyproject.toml）
# 安装 just：https://github.com/casey/just#packages

pdf_url := "https://www.unicode.org/Public/18.0.0/charts/PDF/U3D000.pdf"

# 全流程：提取 → dist/ 四款 OTF → 门禁（任何一项失败即非零退出）
otf: pdf
    uv run xiaozhuan-fonts

# 下载 Unicode 18.0 码表（约 40MB，已存在则跳过）
pdf:
    test -f U3D000.pdf || curl -fL -o U3D000.pdf {{pdf_url}}

# 仅跑门禁
check:
    uv run xiaozhuan-fonts check

# 门禁＋工作区清洁检查＋sha256 清单
release: otf
    #!/bin/sh
    git diff --quiet && git diff --cached --quiet || { echo "工作区不干净"; exit 1; }
    cd dist && { sha256sum 说文小篆-*.otf || shasum -a 256 说文小篆-*.otf; } > sha256sums.txt
    echo "已输出 dist/sha256sums.txt"

# 清理构建产物
clean:
    rm -rf build_svg dist
