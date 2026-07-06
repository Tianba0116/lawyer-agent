# ⚖️ AI 法律助手 — Agent + RAG 智能法律问答框架

基于 **LangChain Agent (ReAct)** + **RAG（检索增强生成）** 的智能法律问答系统，设计为可扩展的基座框架。支持国产大模型、多文档知识库、FAISS 向量检索、SSE 流式输出。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                       Frontend (React)                   │
│  侧边栏导航  │  对话工作区  │  上下文面板                    │
│  模型/知识库  │  SSE 流式渲染 │  文档列表/统计               │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────────┐
│                   Backend (FastAPI)                       │
│                                                          │
│  main.py ── 路由层（query / upload / documents / providers）│
│     │                                                    │
│     ├── agent/ ── Agent 层                               │
│     │   ├── agent.py     create_agent 封装               │
│     │   └── prompts.py   系统提示词                       │
│     │                                                    │
│     ├── tools/ ── 工具层 ★ 核心扩展点                     │
│     │   ├── search.py    语义文档检索                     │
│     │   ├── summarize.py 文档摘要                         │
│     │   └── report.py    报告生成                         │
│     │                                                    │
│     ├── rag/ ── 检索层                                    │
│     │   ├── chunker.py   PDF解析 + 文本切块               │
│     │   ├── vector_db.py FAISS多文档索引                  │
│     │   └── retriever.py 检索策略封装                     │
│     │                                                    │
│     └── core/ ── 基础设施                                 │
│         ├── config.py   配置管理                          │
│         └── llm.py      LLM工厂                          │
│                                                          │
│  providers.json ── LLM供应商定义（可编辑）                  │
│  providers.py   ── 供应商CRUD                             │
└─────────────────────────────────────────────────────────┘
```

### Agent 执行循环 (ReAct)

```
用户提问
  → SystemMessage 注入上下文（是否上传文档）
  → LLM 推理：需要工具吗？
       ├── 是 → 调用 search_legal_document / summarize_document
       │        工具返回结果 → LLM 再次推理 → 需要更多工具？
       │           ├── 是 → 继续调用工具
       │           └── 否 → 综合回答
       └── 否 → 直接回答
  → SSE 逐 token 流式输出到前端
  → 对话历史保存（SystemMessage 不入历史）
```

---

## 项目结构

```
├── README.md
├── LICENSE
│
├── backend/                        # Python 后端
│   ├── main.py                     # FastAPI 入口（路由定义）
│   ├── .env                        # API Key + 基础设施配置
│   ├── providers.json              # LLM 供应商定义 ★ 唯一数据源
│   ├── providers.py                # 供应商 CRUD 操作
│   │
│   ├── core/                       # 基础设施
│   │   ├── config.py               # chunking / embedding / paths 配置
│   │   └── llm.py                  # LLM 工厂（从 providers.json 读取）
│   │
│   ├── rag/                        # RAG 检索管线
│   │   ├── chunker.py              # PDF 加载 + RecursiveCharacterTextSplitter
│   │   ├── vector_db.py            # FAISS 索引（多文档追加、删除重建）
│   │   └── retriever.py            # 检索策略封装
│   │
│   ├── tools/                      # Agent 工具集 ★ 扩展点
│   │   ├── __init__.py             # ALL_TOOLS 注册表
│   │   ├── search.py               # 语义检索
│   │   ├── summarize.py            # 文档摘要
│   │   └── report.py               # 报告生成
│   │
│   ├── agent/                      # Agent 核心
│   │   ├── agent.py                # create_agent 封装 + 状态构建
│   │   └── prompts.py              # 系统提示词
│   │
│   ├── pdfs/                       # 上传的 PDF 文件
│   └── vectorstore/                # FAISS 索引 + 文档注册表
│
└── frontend/                       # React 前端
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                 # 主组件（对话 / 知识库 / 模型 三视图）
        ├── index.css               # 全局样式（政务蓝白主题）
        └── main.jsx                # 入口
```

---

## 数据流

### LLM 供应商选择

```
用户在前端选模型 → PUT /api/providers/{id}/activate
                    ↓
              providers.json: { "active": "deepseek" }
                    ↓
用户提问 → main.py: get_active() → "deepseek"
           llm.py: get_provider("deepseek") → { model, type, api_key_env, base_url }
           llm.py: os.getenv(api_key_env) → "sk-xxx"
                    ↓
           ChatDeepSeek(model="deepseek-chat", api_key="sk-xxx")
```

### 知识库文档

```
上传 PDF → chunker.py 切块 → FAISS.from_documents → merge_from 追加
                                                            ↓
查询时 → FAISS.similarity_search(k=top_k) → 按 source 过滤 → 返回 chunks
```

### 配置分工

```
providers.json  ← LLM 供应商定义（名称、模型、类型、api_key_env、端点）唯一数据源
.env            ← API Key（敏感信息）+ Embedding 配置
core/config.py  ← 基础设施（chunk_size, top_k, 路径）
```

---

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+

### 方式一：一键脚本（推荐）

```bash
# 1. 初始化环境（自动创建 venv、安装依赖、配置镜像）
./scripts/setup.sh

# 2. 编辑 backend/.env，填入你的 API Key
vim backend/.env
# 至少填入: DEEPSEEK_API_KEY=sk-xxxx

# 3. 启动
./start.sh
```

浏览器打开 **http://localhost:5173**

> **💡 镜像选择**：`setup.sh` 默认使用清华大学 TUNA 镜像，也可指定其他源：
> ```bash
> ./scripts/setup.sh --mirror aliyun     # 阿里云
> ./scripts/setup.sh --mirror ustc       # 中科大
> ./scripts/setup.sh --skip-ocr          # 跳过 PaddleOCR（节省 500MB）
> ```

### 方式二：手动安装

<details>
<summary>展开手动步骤</summary>

#### 1. 配置 API Key

复制并编辑环境变量文件：

```bash
cp .env.example backend/.env
vim backend/.env  # 至少填入 DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

#### 2. 启动后端

```bash
cd backend

# 国内用户推荐用清华镜像：
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 如不需要 OCR 功能，跳过 paddle 相关依赖：
# pip install fastapi uvicorn langchain langchain-deepseek langchain-openai \
#     langchain-community langchain-huggingface langchain-text-splitters \
#     faiss-cpu pdfplumber python-dotenv reportlab sentence-transformers

HF_ENDPOINT=https://hf-mirror.com uvicorn main:app --host 0.0.0.0 --port 8000
```

后端运行在 **http://localhost:8000**

#### 3. 启动前端

```bash
cd frontend

# 国内用户走 npmmirror：
npm install --registry=https://registry.npmmirror.com
npm run dev
```

前端运行在 **http://localhost:5173**

</details>

### 国内镜像一览

| 源 | pip | npm | HuggingFace |
|---|---|---|---|
| 清华 TUNA | `https://pypi.tuna.tsinghua.edu.cn/simple` | `https://registry.npmmirror.com` | `https://hf-mirror.com` |
| 阿里云 | `https://mirrors.aliyun.com/pypi/simple/` | `https://registry.npmmirror.com` | `https://hf-mirror.com` |
| 中科大 | `https://pypi.mirrors.ustc.edu.cn/simple/` | `https://registry.npmmirror.com` | `https://hf-mirror.com` |
| 华为云 | `https://repo.huaweicloud.com/repository/pypi/simple` | `https://mirrors.huaweicloud.com/repository/npm/` | `https://hf-mirror.com` |

> **⚠️ HuggingFace 被墙**：务必设置环境变量 `HF_ENDPOINT=https://hf-mirror.com`，否则 Embedding 模型（sentence-transformers）下载失败。`setup.sh` 已自动处理。

---

## API 端点

### 对话

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/query` | 普通问答（返回完整结果） |
| `POST` | `/api/query/stream` | SSE 流式问答（逐 token 推送） |
| `POST` | `/api/summarize` | 生成文档摘要 |

### 知识库

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/upload` | 上传 PDF 并索引 |
| `GET` | `/api/documents` | 列出知识库文档 |
| `DELETE` | `/api/documents/{name}` | 删除文档并重建索引 |

### 模型管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/providers` | 获取所有 LLM 供应商 |
| `POST` | `/api/providers` | 新增自定义供应商 |
| `PUT` | `/api/providers/{id}` | 编辑供应商配置 |
| `PUT` | `/api/providers/{id}/activate` | 切换当前供应商 |
| `DELETE` | `/api/providers/{id}` | 删除自定义供应商 |

### 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/report/{file_name}` | 下载对话报告 PDF |

---

## 扩展指南

### 添加新工具（Agent Skill）

1. 在 `backend/tools/` 下新建文件，用 `@tool` 装饰器定义：

```python
# backend/tools/citation.py
from langchain_core.tools import tool

@tool
def check_citation(query: str, file_name: str = "") -> str:
    """检查法律文书中引用的法条是否准确。"""
    # 实现检索 + 校验逻辑
    return result
```

2. 在 `backend/tools/__init__.py` 注册：

```python
from tools.citation import check_citation
ALL_TOOLS.append(check_citation)
```

3. 更新 `backend/agent/prompts.py` 中的工具描述。

Agent 自动学会使用新工具，无需修改 Agent 核心代码。

### 添加新 LLM 供应商

方式一：前端「模型」页 → 点击「＋ 添加模型」→ 填表保存。

方式二：直接编辑 `backend/providers.json`：

```json
{
  "id": "custom-provider",
  "name": "自定义模型",
  "icon": "🤖",
  "model": "model-name",
  "type": "openai",
  "api_key_env": "MY_API_KEY",
  "base_url": "https://api.example.com/v1",
  "builtin": false
}
```

支持三种 `type`：
- `deepseek` — DeepSeek 官方 SDK
- `openai` — 任何 OpenAI 兼容 API（通义千问、Kimi、GLM、豆包...）
- 只需填 `base_url` + `api_key_env`

### 调整 RAG 参数

编辑 `backend/.env`：

```env
CHUNK_SIZE=1000      # 文本块大小（默认 1000）
CHUNK_OVERLAP=200    # 块重叠（默认 200）
TOP_K=5              # 检索返回数（默认 5）
```

### 切换 Embedding 模型

```env
EMBED_PROVIDER=huggingface              # huggingface / ollama
HF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 框架 | LangChain `create_agent` (ReAct) |
| LLM | DeepSeek / 通义千问 / Kimi / GLM / 豆包（可编辑新增） |
| 向量库 | FAISS + HuggingFace sentence-transformers |
| 后端 | FastAPI + SSE 流式输出 |
| 前端 | React 19 + Vite + react-markdown + remark-gfm |

## License

MIT
