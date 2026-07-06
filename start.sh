#!/usr/bin/env bash
# ==========================================
#  AI 法律助手 — 一键启动脚本（国产镜像版）
# ==========================================
set -e

# ── 镜像源配置（可按需替换）─────────────────
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
NPM_MIRROR="https://registry.npmmirror.com"
HF_MIRROR="https://hf-mirror.com"

# ── 颜色 ──────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
# 优先使用独立 .venv/（dev.sh 创建的），fallback 到 backend/venv/
if [ -d "$PROJECT_DIR/.venv" ]; then
  VENV_DIR="$PROJECT_DIR/.venv"
else
  VENV_DIR="$BACKEND_DIR/venv"
fi

PID_BACKEND=""
PID_FRONTEND=""

# ── 清理：Ctrl+C 同时关掉前后端 ────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务...${NC}"
    if [ -n "$PID_BACKEND" ] && kill -0 "$PID_BACKEND" 2>/dev/null; then
        kill "$PID_BACKEND" 2>/dev/null
        echo -e "${GREEN}✓ 后端已停止${NC}"
    fi
    if [ -n "$PID_FRONTEND" ] && kill -0 "$PID_FRONTEND" 2>/dev/null; then
        kill "$PID_FRONTEND" 2>/dev/null
        echo -e "${GREEN}✓ 前端已停止${NC}"
    fi
    echo -e "${GREEN}再见！${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${CYAN}  ⚖️  AI 法律助手 — 一键启动${NC}"
echo -e "${CYAN}  镜像: 清华(pip) / npmmirror(npm) / hf-mirror${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""

# ==========================================
# Step 1: 环境检查
# ==========================================
echo -e "${CYAN}[1/5]${NC} 检查运行环境..."

PYTHON_VERSION=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo "0.0")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo -e "${RED}✗ 需要 Python 3.10 ~ 3.13，当前版本: $PYTHON_VERSION${NC}"
    exit 1
fi
if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 14 ]; then
    echo -e "${RED}✗ Python $PYTHON_VERSION 暂不支持（PaddlePaddle 最高支持 3.13）${NC}"
    echo -e "${YELLOW}  请用 Python 3.12 或 3.13${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Python $PYTHON_VERSION${NC}"

NODE_VERSION=$(node --version 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}✗ 需要 Node.js 18+，当前版本: $(node --version 2>/dev/null || echo '未安装')${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Node.js $(node --version)${NC}"

# ==========================================
# Step 2: 创建 venv + 配置镜像源
# ==========================================
echo -e "${CYAN}[2/5]${NC} 创建虚拟环境 & 配置镜像..."

# --- 创建 Python venv ---
if [ ! -d "$VENV_DIR" ]; then
    echo "  创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# --- pip 持久化镜像（写入 venv 的 pip.conf）---
PIP_HOST=$(echo "$PIP_MIRROR" | sed -e 's|^https\?://||' -e 's|/.*$||')
mkdir -p "$VENV_DIR"
cat > "$VENV_DIR/pip.conf" << EOF
[global]
index-url = ${PIP_MIRROR}
trusted-host = ${PIP_HOST}
EOF
echo "  ✓ pip 镜像 → ${PIP_MIRROR}"

# --- npm 全局镜像 ---
npm config set registry "$NPM_MIRROR" 2>/dev/null || true
echo "  ✓ npm 镜像 → ${NPM_MIRROR}"

# --- HuggingFace 镜像（环境变量，sentence-transformers 用）---
export HF_ENDPOINT="$HF_MIRROR"
echo "  ✓ HF 镜像 → ${HF_MIRROR}"

echo -e "  ${GREEN}✓ 镜像源配置完成${NC}"

# ==========================================
# Step 3: 后端依赖安装
# ==========================================
echo -e "${CYAN}[3/5]${NC} 安装后端 Python 依赖..."

cd "$BACKEND_DIR"

if [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo "  正在安装（首次约 2-5 分钟，走清华镜像）..."
    echo "  ℹ 首次安装包含 PaddleOCR (~500MB)，可能需要 3-5 分钟"
    pip install -r requirements.txt
    touch "$VENV_DIR/.deps_installed"
    echo -e "  ${GREEN}✓ Python 依赖安装完成${NC}"
else
    echo -e "  ${GREEN}✓ Python 依赖已就绪（跳过）${NC}"
fi

# --- 检查 .env ---
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "  ${YELLOW}⚠ 未找到 backend/.env，自动生成模板...${NC}"
    cat > "$BACKEND_DIR/.env" << 'ENVEOF'
# ── LLM API Keys（至少填一个）────────────────
DEEPSEEK_API_KEY=sk-your-key-here
# QWEN_API_KEY=
# MOONSHOT_API_KEY=
# ZHIPU_API_KEY=
# DOUBAO_API_KEY=

# ── HuggingFace 镜像（国内必配）─────────────
HF_ENDPOINT=https://hf-mirror.com

# ── RAG 参数 ────────────────────────────────
EMBED_PROVIDER=huggingface
HF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K=5
ENVEOF
    echo -e "  ${YELLOW}⚠ 请编辑 backend/.env，至少填入一个 API Key！${NC}"
fi

# ==========================================
# Step 4: 前端依赖安装
# ==========================================
echo -e "${CYAN}[4/5]${NC} 安装前端 Node.js 依赖..."

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "  正在安装（首次约 1-3 分钟，走 npmmirror）..."
    npm install
    echo -e "  ${GREEN}✓ Node.js 依赖安装完成${NC}"
else
    echo -e "  ${GREEN}✓ Node.js 依赖已就绪（跳过）${NC}"
fi

# ==========================================
# Step 5: 启动前后端
# ==========================================
echo -e "${CYAN}[5/5]${NC} 启动前后端服务..."
echo ""

# 启动后端（注入 HF_ENDPOINT 确保模型下载走镜像）
cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"
export HF_ENDPOINT="$HF_MIRROR"
uvicorn main:app --host 0.0.0.0 --port 8000 &
PID_BACKEND=$!

# 启动前端
cd "$FRONTEND_DIR"
npm run dev &
PID_FRONTEND=$!

sleep 2

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 全部启动完成！${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo -e "  后端 API:  ${CYAN}http://localhost:8000${NC}"
echo -e "  前端界面:  ${CYAN}http://localhost:5173${NC}"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

wait
