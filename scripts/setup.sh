#!/usr/bin/env bash
# ============================================================
#  AI 法律助手 — 新机初始化脚本（国产镜像版）
# ============================================================
#  功能：一键完成虚拟环境创建、依赖安装、配置生成
#  适用：macOS / Linux（Windows 请用 Git Bash 或 WSL）
#
#  用法：
#    chmod +x scripts/setup.sh
#    ./scripts/setup.sh              # 交互式选择镜像
#    ./scripts/setup.sh --mirror tsinghua   # 指定镜像（跳过交互）
#    ./scripts/setup.sh --mirror aliyun
#    ./scripts/setup.sh --mirror ustc
#    ./scripts/setup.sh --skip-ocr   # 跳过 PaddleOCR（节省 500MB）
# ============================================================
set -e

# ── 镜像源配置 ──────────────────────────────
# 每个镜像定义: 名称|pip地址|npm地址|hf地址
MIRRORS=(
  "清华 (TUNA)|https://pypi.tuna.tsinghua.edu.cn/simple|https://registry.npmmirror.com|https://hf-mirror.com"
  "阿里云|https://mirrors.aliyun.com/pypi/simple/|https://registry.npmmirror.com|https://hf-mirror.com"
  "腾讯云|https://mirrors.cloud.tencent.com/pypi/simple|https://registry.npmmirror.com|https://hf-mirror.com"
  "中科大 (USTC)|https://pypi.mirrors.ustc.edu.cn/simple/|https://registry.npmmirror.com|https://hf-mirror.com"
  "华为云|https://repo.huaweicloud.com/repository/pypi/simple|https://mirrors.huaweicloud.com/repository/npm/|https://hf-mirror.com"
  "官方源 (无镜像)|https://pypi.org/simple/|https://registry.npmjs.org|https://huggingface.co"
)

# ── 颜色 ──────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 路径 ──────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"   # 独立虚拟环境，不与已有 backend/venv/ 冲突
SCRIPTS_DIR="$PROJECT_DIR/scripts"

SKIP_OCR=false
SELECTED_MIRROR=""

# ── Banner ────────────────────────────────
banner() {
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║${NC}     ${BOLD}⚖️  AI 法律助手 — 环境初始化${NC}                       ${CYAN}║${NC}"
  echo -e "${CYAN}║${NC}     LangChain Agent + RAG + FAISS 向量检索              ${CYAN}║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
}

# ── 解析参数 ──────────────────────────────
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mirror)
        SELECTED_MIRROR="$2"
        shift 2
        ;;
      --skip-ocr)
        SKIP_OCR=true
        shift
        ;;
      --help|-h)
        echo "用法: ./scripts/setup.sh [选项]"
        echo ""
        echo "选项:"
        echo "  --mirror <名称>   指定镜像源 (tsinghua|aliyun|tencent|ustc|huawei|official)"
        echo "  --skip-ocr        跳过 PaddleOCR 安装（节省 ~500MB 下载）"
        echo "  --help, -h        显示此帮助"
        echo ""
        echo "镜像列表:"
        echo "  tsinghua  - 清华大学 TUNA (推荐)"
        echo "  aliyun    - 阿里云"
        echo "  tencent   - 腾讯云"
        echo "  ustc      - 中科大 USTC"
        echo "  huawei    - 华为云"
        echo "  official  - 官方源（不使用镜像）"
        exit 0
        ;;
      *)
        echo -e "${RED}未知参数: $1${NC}"
        exit 1
        ;;
    esac
  done
}

# ── 交互式选择镜像 ─────────────────────────
select_mirror() {
  local choice

  echo -e "${YELLOW}请选择软件镜像源:${NC}"
  echo ""
  for i in "${!MIRRORS[@]}"; do
    IFS='|' read -r name pip_url npm_url hf_url <<< "${MIRRORS[$i]}"
    printf "  ${GREEN}%d)${NC} %s\n" "$((i+1))" "$name"
  done
  echo ""

  while true; do
    printf "输入编号 ${BLUE}[1-%d]${NC}（默认 1）: " "${#MIRRORS[@]}"
    read -r choice
    choice="${choice:-1}"
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#MIRRORS[@]}" ]; then
      SELECTED_MIRROR="${MIRRORS[$((choice-1))]}"
      break
    fi
    echo -e "${RED}请输入 1-${#MIRRORS[@]} 之间的数字${NC}"
  done
}

# ── 获取镜像设置 ───────────────────────────
get_mirror_config() {
  if [ -n "$SELECTED_MIRROR" ] && [[ "$SELECTED_MIRROR" != *"|"* ]]; then
    # 短名称匹配
    case "$SELECTED_MIRROR" in
      tsinghua) SELECTED_MIRROR="${MIRRORS[0]}" ;;
      aliyun)   SELECTED_MIRROR="${MIRRORS[1]}" ;;
      tencent)  SELECTED_MIRROR="${MIRRORS[2]}" ;;
      ustc)     SELECTED_MIRROR="${MIRRORS[3]}" ;;
      huawei)   SELECTED_MIRROR="${MIRRORS[4]}" ;;
      official) SELECTED_MIRROR="${MIRRORS[5]}" ;;
      *) echo -e "${RED}未知镜像: $SELECTED_MIRROR${NC}"; exit 1 ;;
    esac
  elif [ -z "$SELECTED_MIRROR" ]; then
    select_mirror
  fi

  IFS='|' read -r MIRROR_NAME PIP_MIRROR NPM_MIRROR HF_MIRROR <<< "$SELECTED_MIRROR"
}

# ── 步骤 1: 环境检查 ───────────────────────
check_prerequisites() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[1/6] 检查运行环境...${NC}"
  echo ""

  # Python
  if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo "0.0")
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
      echo -e "  ${RED}✗ Python 版本过低: $PYTHON_VERSION（需要 3.10+）${NC}"
      echo -e "  ${YELLOW}  请安装 Python 3.10+: https://www.python.org/downloads/${NC}"
      exit 1
    fi
    echo -e "  ${GREEN}✓${NC} Python $(python3 --version)"
  else
    echo -e "  ${RED}✗ 未找到 python3，请先安装 Python 3.10+${NC}"
    exit 1
  fi

  # Node.js
  if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
    if [ "$NODE_VERSION" -lt 18 ]; then
      echo -e "  ${RED}✗ Node.js 版本过低: $(node --version)（需要 18+）${NC}"
      exit 1
    fi
    echo -e "  ${GREEN}✓${NC} Node.js $(node --version)"
  else
    echo -e "  ${RED}✗ 未找到 node，请先安装 Node.js 18+${NC}"
    echo -e "  ${YELLOW}  推荐使用 nvm: https://nvm.uihtm.com${NC}"
    exit 1
  fi

  # pip
  if command -v pip3 &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} pip $(pip3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)"
  fi

  # npm
  if command -v npm &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} npm $(npm --version)"
  fi

  echo ""
  echo -e "  ${GREEN}环境检查通过 ✓${NC}"
  echo ""
}

# ── 步骤 2: 创建虚拟环境 ────────────────────
setup_venv() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[2/6] 创建 Python 虚拟环境...${NC}"
  echo ""

  if [ -d "$VENV_DIR" ]; then
    echo -e "  ${YELLOW}虚拟环境已存在，跳过创建${NC}"
  else
    echo "  正在创建 venv..."
    python3 -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓ venv 创建完成${NC}"
  fi

  # 激活 venv
  source "$VENV_DIR/bin/activate"

  # ── 持久化 pip 镜像配置（写入 venv）──────
  PIP_HOST=$(echo "$PIP_MIRROR" | sed -e 's|^https\?://||' -e 's|/.*$||')
  mkdir -p "$VENV_DIR"
  cat > "$VENV_DIR/pip.conf" << PIPEOF
[global]
index-url = ${PIP_MIRROR}
trusted-host = ${PIP_HOST}
PIPEOF
  echo -e "  ${GREEN}✓${NC} pip 镜像 → ${MIRROR_NAME}"
  echo -e "  ${GREEN}✓${NC} pip.conf 已写入 venv（后续 pip install 自动走镜像）"
  echo ""

  # ── 升级 pip ──────────────────────────
  echo "  升级 pip..."
  pip install --quiet --upgrade pip 2>&1 | tail -1 || true
}

# ── 步骤 3: 安装 Python 依赖 ────────────────
install_python_deps() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[3/6] 安装 Python 后端依赖...${NC}"
  echo ""

  source "$VENV_DIR/bin/activate"
  cd "$BACKEND_DIR"

  # 如果需要跳过 OCR，先生成一个临时 requirements
  if $SKIP_OCR; then
    echo -e "  ${YELLOW}⚠ OCR 模式已跳过（--skip-ocr）${NC}"
    echo "  正在生成不含 OCR 的临时依赖列表..."
    grep -v "paddlepaddle\|paddleocr\|paddlex\|pymupdf" requirements.txt > /tmp/requirements_no_ocr.txt
    REQ_FILE="/tmp/requirements_no_ocr.txt"
  else
    REQ_FILE="requirements.txt"
  fi

  echo "  正在安装依赖（首次约 2-5 分钟，走 ${MIRROR_NAME} 镜像）..."

  if $SKIP_OCR; then
    echo "  ℹ 基础模式安装中..."
  else
    echo "  ℹ 完整模式（含 OCR ~500MB）安装中..."
  fi

  # 安装
  pip install -r "$REQ_FILE" 2>&1 | while IFS= read -r line; do
    # 只显示关键行
    if [[ "$line" =~ (Successfully|ERROR|error|Collecting|Downloading) ]]; then
      echo "  $line"
    fi
  done

  local pip_exit_code=${PIPESTATUS[0]}
  if [ "$pip_exit_code" -ne 0 ]; then
    echo ""
    echo -e "  ${RED}✗ pip 安装失败${NC}"
    echo -e "  ${YELLOW}  常见原因:${NC}"
    echo -e "  ${YELLOW}  1. 网络问题 → 尝试切换镜像: ./scripts/setup.sh --mirror aliyun${NC}"
    echo -e "  ${YELLOW}  2. 磁盘空间不足 → PaddleOCR 需要 ~2GB 空闲空间${NC}"
    echo -e "  ${YELLOW}  3. Python 版本不兼容 → 确保 Python 3.10+${NC}"
    echo -e "  ${YELLOW}  4. 跳过 OCR 重试: ./scripts/setup.sh --skip-ocr${NC}"
    exit 1
  fi

  # 标记已安装
  touch "$VENV_DIR/.deps_installed"
  echo ""
  echo -e "  ${GREEN}✓ Python 依赖安装完成${NC}"
  echo ""
}

# ── 步骤 4: 安装 Node.js 依赖 ───────────────
install_node_deps() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[4/6] 安装前端 Node.js 依赖...${NC}"
  echo ""

  cd "$FRONTEND_DIR"

  # 设置 npm 镜像
  npm config set registry "$NPM_MIRROR" 2>/dev/null || true
  echo -e "  ${GREEN}✓${NC} npm 镜像 → ${NPM_MIRROR}"

  if [ -d "node_modules" ]; then
    echo -e "  ${YELLOW}node_modules 已存在，跳过安装${NC}"
  else
    echo "  正在安装（首次约 1-3 分钟）..."
    npm install 2>&1 | while IFS= read -r line; do
      if [[ "$line" =~ (added|error|ERR) ]]; then
        echo "  $line"
      fi
    done

    if [ "${PIPESTATUS[0]}" -ne 0 ]; then
      echo -e "  ${RED}✗ npm 安装失败${NC}"
      echo -e "  ${YELLOW}  请尝试: npm install --registry=https://registry.npmmirror.com${NC}"
      exit 1
    fi
  fi

  echo -e "  ${GREEN}✓ Node.js 依赖安装完成${NC}"
  echo ""
}

# ── 步骤 5: 配置环境变量 ────────────────────
setup_env() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[5/6] 配置环境变量...${NC}"
  echo ""

  cd "$PROJECT_DIR"

  # .env
  if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "  生成 backend/.env 模板..."
    cat > "$BACKEND_DIR/.env" << 'ENVEOF'
# ═══════════════════════════════════════════
#  AI 法律助手 — 环境变量配置
# ═══════════════════════════════════════════

# ── LLM API Key（至少填一个！）────────────
DEEPSEEK_API_KEY=sk-your-key-here
# QWEN_API_KEY=
# MOONSHOT_API_KEY=
# ZHIPU_API_KEY=
# DOUBAO_API_KEY=

# ── HuggingFace 镜像（国内必配）───────────
HF_ENDPOINT=https://hf-mirror.com

# ── RAG 参数（可选）───────────────────────
EMBED_PROVIDER=huggingface
HF_EMBED_MODEL=BAAI/bge-small-zh-v1.5
# CHUNK_SIZE=1000
# CHUNK_OVERLAP=200
# TOP_K=5

# ── OCR 参数（可选）───────────────────────
# OCR_DPI=150
# OCR_TABLE_RECOGNITION=1
# OCR_MODE=accurate
ENVEOF
    echo -e "  ${GREEN}✓${NC} .env 模板已生成"
    echo ""
    echo -e "  ${YELLOW}⚠ 重要！请编辑 backend/.env，至少填入一个 API Key:${NC}"
    echo -e "  ${YELLOW}  vim backend/.env${NC}"
    echo -e "  ${YELLOW}  或双击 backend/.env 用编辑器打开${NC}"
  else
    echo -e "  ${YELLOW}backend/.env 已存在，跳过${NC}"
  fi

  echo ""
}

# ── 步骤 6: 下载 Embedding 模型 ─────────────
warmup_embed_model() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}[6/6] 预热 Embedding 模型...${NC}"
  echo ""

  source "$VENV_DIR/bin/activate"
  export HF_ENDPOINT="$HF_MIRROR"

  local model_name="${HF_EMBED_MODEL:-BAAI/bge-small-zh-v1.5}"

  echo "  首次运行会自动下载 Embedding 模型（~100MB）"
  echo "  正在预下载: ${model_name}..."

  python3 -c "
import os
os.environ['HF_ENDPOINT'] = '${HF_MIRROR}'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('${model_name}')
print(f'  ✓ 模型加载成功: {model.get_sentence_embedding_dimension()} 维向量')
" 2>&1 || {
    echo ""
    echo -e "  ${YELLOW}⚠ 模型预下载失败（不影响环境配置）${NC}"
    echo -e "  ${YELLOW}  首次启动时会自动重试下载${NC}"
    echo -e "  ${YELLOW}  如持续失败，请检查 HF_ENDPOINT 设置: https://hf-mirror.com${NC}"
  }

  echo ""
}

# ── 完成提示 ───────────────────────────────
print_summary() {
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║           ✅ 环境初始化完成！                      ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${BOLD}镜像源:${NC} ${MIRROR_NAME}"
  echo -e "  ${BOLD}Python:${NC}  $(python3 --version)  (venv: backend/venv)"
  echo -e "  ${BOLD}Node:${NC}   $(node --version)"
  echo ""
  echo -e "  ${BOLD}下一步:${NC}"
  echo ""
  echo -e "  ${CYAN}1)${NC} ${BOLD}配置 API Key${NC}"
  echo -e "     vim backend/.env"
  echo -e "     至少填入 DEEPSEEK_API_KEY=sk-xxxx"
  echo ""
  echo -e "  ${CYAN}2)${NC} ${BOLD}启动服务${NC}"
  echo -e "     ./start.sh"
  echo ""
  echo -e "  ${CYAN}3)${NC} 打开浏览器 → ${BLUE}http://localhost:5173${NC}"
  echo ""
  echo -e "  ${BOLD}更多帮助:${NC}"
  echo -e "  ${BOLD}•${NC} 切换镜像: ${BLUE}./scripts/setup.sh --mirror aliyun${NC}"
  echo -e "  ${BOLD}•${NC} 仅安装基础依赖（跳过 OCR）: ${BLUE}./scripts/setup.sh --skip-ocr${NC}"
  echo -e "  ${BOLD}•${NC} 查看 README: ${BLUE}cat README.md${NC}"
  echo ""
}

# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
main() {
  parse_args "$@"
  banner
  get_mirror_config
  check_prerequisites
  setup_venv
  install_python_deps
  install_node_deps
  setup_env
  warmup_embed_model
  print_summary
}

main "$@"
