#!/usr/bin/env bash
# ============================================================
#  AI 法律助手 — OCR 扫描件支持安装（可选模块）
# ============================================================
#  功能：单独安装 PaddleOCR 相关依赖（~500MB 下载）
#  适用：需要处理扫描件/图片型 PDF 的场景
#
#  用法：
#    ./scripts/setup_ocr.sh              # 交互式选择镜像
#    ./scripts/setup_ocr.sh --mirror tsinghua
# ============================================================
set -e

# ── 镜像 ──────────────────────────────────
MIRRORS=(
  "清华 (TUNA)|https://pypi.tuna.tsinghua.edu.cn/simple"
  "阿里云|https://mirrors.aliyun.com/pypi/simple/"
  "腾讯云|https://mirrors.cloud.tencent.com/pypi/simple"
  "中科大 (USTC)|https://pypi.mirrors.ustc.edu.cn/simple/"
  "华为云|https://repo.huaweicloud.com/repository/pypi/simple"
  "官方源|https://pypi.org/simple/"
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$PROJECT_DIR/.venv"   # 与 dev.sh / setup.sh 保持一致
SELECTED_MIRROR=""

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mirror)
        case "$2" in
          tsinghua) SELECTED_MIRROR="${MIRRORS[0]}" ;;
          aliyun)   SELECTED_MIRROR="${MIRRORS[1]}" ;;
          tencent)  SELECTED_MIRROR="${MIRRORS[2]}" ;;
          ustc)     SELECTED_MIRROR="${MIRRORS[3]}" ;;
          huawei)   SELECTED_MIRROR="${MIRRORS[4]}" ;;
          official) SELECTED_MIRROR="${MIRRORS[5]}" ;;
          *) echo -e "${RED}未知镜像: $2${NC}"; exit 1 ;;
        esac
        shift 2
        ;;
      --help|-h)
        echo "用法: ./scripts/setup_ocr.sh [--mirror <名称>]"
        echo ""
        echo "单独安装 PaddleOCR 依赖（如果之前在 setup.sh 中使用了 --skip-ocr）"
        exit 0
        ;;
      *) shift ;;
    esac
  done
}

select_mirror() {
  if [ -z "$SELECTED_MIRROR" ]; then
    echo -e "${YELLOW}选择 pip 镜像:${NC}"
    for i in "${!MIRRORS[@]}"; do
      IFS='|' read -r name url <<< "${MIRRORS[$i]}"
      echo "  $((i+1))) $name"
    done
    printf "输入 [1-6]（默认 1）: "
    read -r c; c="${c:-1}"
    SELECTED_MIRROR="${MIRRORS[$((c-1))]}"
  fi
  IFS='|' read -r MIRROR_NAME PIP_MIRROR <<< "$SELECTED_MIRROR"
}

main() {
  parse_args "$@"

  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║       🔍 PaddleOCR 扫描件支持 — 安装              ║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""

  select_mirror

  # 检查 venv
  if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}✗ 未找到虚拟环境，请先运行 ./scripts/setup.sh${NC}"
    exit 1
  fi

  source "$VENV_DIR/bin/activate"

  # 配置 pip 镜像
  PIP_HOST=$(echo "$PIP_MIRROR" | sed -e 's|^https\?://||' -e 's|/.*$||')
  mkdir -p "$VENV_DIR"
  cat > "$VENV_DIR/pip.conf" << EOF
[global]
index-url = ${PIP_MIRROR}
trusted-host = ${PIP_HOST}
EOF

  echo -e "${BLUE}安装 PaddleOCR 相关依赖（镜像: ${MIRROR_NAME}）${NC}"
  echo -e "${YELLOW}⚠ 下载约 500MB，预计 3-5 分钟${NC}"
  echo ""

  pip install paddlepaddle==3.2.2 paddleocr>=3.5.0 "paddlex[ocr]" pymupdf

  # 验证
  echo ""
  echo "验证安装..."
  python3 -c "
import paddleocr
from paddleocr import PaddleOCR
print('  ✓ PaddleOCR 安装成功')
print(f'  版本: {paddleocr.__version__}')
" 2>&1 || echo -e "${YELLOW}  ⚠ 验证失败，但可能仍可使用${NC}"

  echo ""
  echo -e "${GREEN}✓ OCR 模块安装完成${NC}"
  echo ""
  echo "  用法参考: python orc_pdf/ocr_extract.py"
}

main "$@"
