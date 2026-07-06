#!/usr/bin/env bash
# ================================================================
#  ⚖️  AI 法律助手 — 开发环境一键启动（独立虚拟环境）
# ================================================================
#  用法:
#    ./dev.sh                     # 自动创建 .venv → 安装依赖 → 启动
#    ./dev.sh --skip-ocr          # 跳过 PaddleOCR（节省 ~500MB）
#    ./dev.sh --mirror aliyun     # 使用阿里云镜像
#
#  特点:
#    • 使用项目根目录 .venv/（与系统 Python 及已有 venv 完全隔离）
#    • 不修改已有 backend/venv/ 或全局 pip/npm 配置
#    • 首次运行自动安装所有依赖，后续秒启动
#    • 国内镜像默认清华大学 TUNA + npmmirror + hf-mirror
#    • Ctrl+C 同时停止前后端
# ================================================================
set -e

# ═══════════════════════════════════════════════════════════
# 镜像源（可按需替换）
# ═══════════════════════════════════════════════════════════
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
NPM_MIRROR="https://registry.npmmirror.com"
HF_MIRROR="https://hf-mirror.com"

# ═══════════════════════════════════════════════════════════
# 路径 — venv 放在项目根 .venv/，与已有 backend/venv/ 互不干扰
# ═══════════════════════════════════════════════════════════
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# ═══════════════════════════════════════════════════════════
# 颜色
# ═══════════════════════════════════════════════════════════
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SKIP_OCR=false

# ═══════════════════════════════════════════════════════════
# 参数解析
# ═══════════════════════════════════════════════════════════
for arg in "$@"; do
  case "$arg" in
    --skip-ocr) SKIP_OCR=true ;;
    --mirror)
      # 由下一个参数处理
      ;;
    aliyun)
      PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
      NPM_MIRROR="https://registry.npmmirror.com"
      ;;
    tsinghua)
      PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
      NPM_MIRROR="https://registry.npmmirror.com"
      ;;
    ustc)
      PIP_MIRROR="https://pypi.mirrors.ustc.edu.cn/simple/"
      NPM_MIRROR="https://registry.npmmirror.com"
      ;;
    huawei)
      PIP_MIRROR="https://repo.huaweicloud.com/repository/pypi/simple"
      NPM_MIRROR="https://mirrors.huaweicloud.com/repository/npm/"
      ;;
    tencent)
      PIP_MIRROR="https://mirrors.cloud.tencent.com/pypi/simple"
      NPM_MIRROR="https://registry.npmmirror.com"
      ;;
    *) ;;
  esac
done

PIP_HOST=$(echo "$PIP_MIRROR" | sed -e 's|^https\?://||' -e 's|/.*$||')

# ═══════════════════════════════════════════════════════════
# Ctrl+C 清理
# ═══════════════════════════════════════════════════════════
PID_BACKEND=""
PID_FRONTEND=""
cleanup() {
  echo ""
  echo -e "${YELLOW}正在关闭服务...${NC}"
  [ -n "$PID_BACKEND" ] && kill "$PID_BACKEND" 2>/dev/null && echo -e "  ${GREEN}✓ 后端已停止${NC}" || true
  [ -n "$PID_FRONTEND" ] && kill "$PID_FRONTEND" 2>/dev/null && echo -e "  ${GREEN}✓ 前端已停止${NC}" || true
  echo -e "${GREEN}再见！${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ═══════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}     ${BOLD}⚖️  AI 法律助手 — 开发环境${NC}                          ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}     独立 venv: .venv/  镜像: 清华/npmmirror/hf-mirror     ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════
# Step 1 — 环境检查
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [1] 检查运行环境 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Python
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}✗ 未找到 python3，请安装 Python 3.10 ~ 3.13${NC}"
  echo -e "  macOS: brew install python@3.12"
  echo -e "  Ubuntu: sudo apt install python3.12 python3.12-venv"
  exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo -e "${RED}✗ Python 版本过低: $PY_VER（需要 3.10 ~ 3.13）${NC}"
  exit 1
fi
if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 14 ]; then
  echo -e "${RED}✗ Python $PY_VER 暂不支持${NC}"
  echo -e "${YELLOW}  PaddlePaddle 最高支持 Python 3.13，没有 cp314 wheel${NC}"
  echo -e "${YELLOW}  请安装 Python 3.12 或 3.13 后重试:${NC}"
  echo -e "${YELLOW}    macOS:  brew install python@3.12${NC}"
  echo -e "${YELLOW}    Ubuntu: sudo apt install python3.12 python3.12-venv${NC}"
  echo -e "${YELLOW}    pyenv:  pyenv install 3.12.4 && pyenv local 3.12.4${NC}"
  echo -e "${YELLOW}  或跳过 OCR: ./dev.sh --skip-ocr${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $PY_VER"

# Node
if ! command -v node &>/dev/null; then
  echo -e "${RED}✗ 未找到 node，请安装 Node.js 18+${NC}"
  echo -e "  macOS: brew install node"
  echo -e "  推荐 nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
  exit 1
fi
NODE_MAJOR=$(node --version | grep -oE '[0-9]+' | head -1)
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo -e "${RED}✗ Node.js 版本过低: $(node --version)（需要 18+）${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} Node.js $(node --version)"
echo ""

# ═══════════════════════════════════════════════════════════
# Step 2 — 创建独立虚拟环境
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [2] 准备虚拟环境 (.venv/) ━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

NEED_PIP_INSTALL=false

if [ ! -d "$VENV_DIR" ]; then
  echo "  创建独立虚拟环境 .venv/ ..."
  python3 -m venv "$VENV_DIR"
  NEED_PIP_INSTALL=true
  echo -e "  ${GREEN}✓ 虚拟环境已创建${NC}"
else
  echo -e "  ${GREEN}✓ 虚拟环境已存在${NC}"
fi

# 激活
source "$VENV_DIR/bin/activate"

# 持久化 pip 镜像配置
cat > "$VENV_DIR/pip.conf" << EOF
[global]
index-url = ${PIP_MIRROR}
trusted-host = ${PIP_HOST}
EOF
echo -e "  ${GREEN}✓${NC} pip.conf → ${PIP_MIRROR}"

# npm 镜像（项目级 .npmrc，不动全局配置）
cat > "$FRONTEND_DIR/.npmrc" << EOF
registry=${NPM_MIRROR}
EOF
echo -e "  ${GREEN}✓${NC} .npmrc → ${NPM_MIRROR}"

# 升级 pip
pip install --quiet --upgrade pip 2>/dev/null || true
echo ""

# ═══════════════════════════════════════════════════════════
# Step 3 — Python 依赖
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [3] Python 后端依赖 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if $NEED_PIP_INSTALL || [ ! -f "$VENV_DIR/.deps_installed" ]; then
  echo "  安装后端依赖 ..."

  # 构建临时 requirements
  if $SKIP_OCR; then
    echo -e "  ${YELLOW}跳过 OCR 依赖 (--skip-ocr)${NC}"
    grep -v "paddlepaddle\|paddleocr\|paddlex\|pymupdf" "$BACKEND_DIR/requirements.txt" > /tmp/req_dev.txt
    REQ_FILE="/tmp/req_dev.txt"
  else
    REQ_FILE="$BACKEND_DIR/requirements.txt"
  fi

  pip install -r "$REQ_FILE" 2>&1 | while IFS= read -r line; do
    case "$line" in
      *Successfully*|*ERROR*|*error*) echo "  $line" ;;
    esac
  done

  if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo ""
    echo -e "${RED}✗ pip install 失败${NC}"
    echo -e "${YELLOW}  重试建议:${NC}"
    echo -e "  ${YELLOW}  • 切换镜像: ./dev.sh --mirror aliyun${NC}"
    echo -e "  ${YELLOW}  • 跳过 OCR: ./dev.sh --skip-ocr${NC}"
    exit 1
  fi

  touch "$VENV_DIR/.deps_installed"
  echo -e "  ${GREEN}✓ Python 依赖安装完成${NC}"
else
  echo -e "  ${GREEN}✓ Python 依赖已就绪（跳过安装）${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════
# Step 4 — Node.js 依赖
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [4] 前端 Node.js 依赖 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  echo "  安装前端依赖 ..."
  npm install 2>&1 | while IFS= read -r line; do
    case "$line" in
      *added*|*error*|*ERR*) echo "  $line" ;;
    esac
  done
  if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}✗ npm install 失败${NC}"
    echo -e "  ${YELLOW}  重试: npm install --registry=https://registry.npmmirror.com${NC}"
    exit 1
  fi
  echo -e "  ${GREEN}✓ Node.js 依赖安装完成${NC}"
else
  echo -e "  ${GREEN}✓ Node.js 依赖已就绪（跳过安装）${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════
# Step 5 — 配置文件
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [5] 检查配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "  生成 backend/.env 模板 ..."
  cat > "$BACKEND_DIR/.env" << 'ENVEOF'
# ═══════════════════════════════════════════
#  AI 法律助手 — 环境变量
# ═══════════════════════════════════════════
# 获取 Key: https://platform.deepseek.com/api_keys

DEEPSEEK_API_KEY=sk-your-key-here
# QWEN_API_KEY=
# MOONSHOT_API_KEY=
# ZHIPU_API_KEY=
# DOUBAO_API_KEY=

# HuggingFace 镜像（国内必须）
HF_ENDPOINT=https://hf-mirror.com

EMBED_PROVIDER=huggingface
HF_EMBED_MODEL=BAAI/bge-small-zh-v1.5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K=5
ENVEOF
  echo -e "  ${YELLOW}⚠ .env 模板已创建（API Key 为空，仅可直接启动测试）${NC}"
  echo -e "  ${YELLOW}  如需使用 AI 对话功能，请编辑 backend/.env 填入 Key${NC}"
else
  echo -e "  ${GREEN}✓ backend/.env 已存在${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════
# Step 6 — 启动
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}━━━ [6] 启动服务 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 后端
cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"
export HF_ENDPOINT="$HF_MIRROR"

echo "  启动后端 (uvicorn) ..."
uvicorn main:app --host 0.0.0.0 --port 8000 &
PID_BACKEND=$!

# 前端
cd "$FRONTEND_DIR"
echo "  启动前端 (vite) ..."
npx vite --host &
PID_FRONTEND=$!

sleep 2

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ 开发环境已就绪                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}后端 API${NC}   ${CYAN}http://localhost:8000${NC}"
echo -e "  ${BOLD}前端界面${NC}   ${CYAN}http://localhost:5173${NC}"
echo -e "  ${BOLD}API 文档${NC}   ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 等待任意子进程退出
wait
