# OCR 扫描件处理 — 经验手册

## 架构概览

```
用户上传 PDF
     │
     ▼
detect_pdf_type()  ── 自动检测文本型 vs 扫描件
     │
     ├── 文本型 → pdfplumber 提取文字 → chunk → FAISS
     │
     └── 扫描件 → PP-StructureV3 OCR → document.md → chunk → FAISS
                    │
                    ├── 布局分析 (PP-DocLayout_plus-L)
                    ├── 文字识别 (PP-OCRv5_server)
                    ├── 表格识别 (SLANeXt + RT-DETR-L)
                    └── 公式识别 (PP-FormulaNet_plus-L)
```

## 关键文件

| 文件 | 职责 |
|---|---|
| `backend/ocr/engine.py` | PDF 类型检测 + PP-StructureV3 OCR 管线 |
| `backend/ocr/metadata.py` | 案号/日期/当事人等元数据自动抽取 |
| `backend/ocr/utils.py` | HTML 表格 → Markdown 转换 |
| `backend/rag/chunker.py` | `load_pdf()` — 扫描件路由 + Document 创建 |
| `backend/core/config.py` | OCR 配置项 |

## 配置项速查

在 `backend/.env` 中设置：

```bash
# ── 精度与速度 ──
OCR_DPI=150                    # 扫描 DPI，默认 150
                               # 120: 极速，适合纯文字
                               # 150: 平衡（推荐）
                               # 200: 高精度，适合小字体/复杂排版

# ── 表格识别 ──
OCR_TABLE_RECOGNITION=1        # 1=开启 0=关闭
                               # 关闭可提速约 50%，跳过 SLANeXt + RT-DETR-L

# ── 预设模式 ──
OCR_MODE=accurate              # accurate: 完整识别（默认）
                               # fast: 快速模式（自动关闭表格识别）
```

### 推荐场景配置

| 场景 | 配置 |
|---|---|
| 判决书/起诉书（正文为主） | `OCR_MODE=fast` — 够快够准 |
| 合同/申报表（含表格） | `OCR_MODE=accurate` — 需要表格 |
| 批量处理 >50 页 | `OCR_MODE=fast` + `OCR_DPI=120` |
| 质量很差的老旧扫描件 | `OCR_DPI=200` — 高 DPI 补偿 |

## PDF 类型检测机制

三重判断 (`detect_pdf_type`):

1. **几乎无文字** → 平均每页 < 50 字符 → 扫描件
2. **空白符比例过高** → 空白符/总字符 > 15% → 噪音文字层 → 扫描件
3. **正常文字** → 文本型

### 已知坑

- 某些扫描软件会在 PDF 中嵌入 OCR 后的文字层，但质量极差（全是乱码）。
  检测通过空白符比例来识别这种情况（乱码文字层往往碎片化严重，空白符很多）。
- 如果发现扫描件被误判为文本型，检查该 PDF 的 `fitz.get_text()` 输出，
  通过空白符比例判断是否需要调整阈值。

## 速度优化总结

| 优化手段 | 提速 | 副作用 | 平台 |
|---|---|---|---|
| DPI 200→150 | ~2x | 小字体可能略微模糊 | 全平台 |
| DPI 150→120 | ~1.5x | 适合纯文字，表格可能不准 | 全平台 |
| 关闭表格识别 | ~2x | 丢失表格内容 | 全平台 |
| MPS GPU (Apple Silicon) | ~1.5-2x | 自动检测，无副作用 | macOS |
| CUDA GPU (NVIDIA) | ~2-3x | 自动检测，无副作用 | Linux/Win |

### GPU 自动检测逻辑

```
1. 检测 Apple MPS → 可用则用
2. 检测 NVIDIA CUDA → 可用则用
3. 都没有 → CPU（全平台通用）
```

当前 PaddlePaddle 3.2.2 在 Apple Silicon 上 MPS 支持处于实验阶段。
如果遇到 MPS 相关错误，设置环境变量禁用：
```bash
# 如果 MPS 报错，强制 CPU
# 需要修改 engine.py 的 _detect_device()，加个环境变量开关
```

## 依赖说明

```
paddlepaddle==3.2.2      # 深度学习框架 (~100MB)
paddleocr>=3.5.0          # OCR 工具包
paddlex[ocr]              # PP-StructureV3 布局/表格/公式模型
pymupdf                   # PDF 渲染为图像 (fitz)
```

- 总计约 1.5GB，首次安装需 3-5 分钟
- 注意: PaddlePaddle 3.3.x 存在 ONEDNN 兼容性问题，锁定 3.2.2
- 不需要 OCR 功能时，不装这些依赖也能正常使用文本型 PDF

## 输出目录结构

```
backend/ocr_output/
└── {文档名}/
    ├── document.md      # 全文（表格已嵌入）
    ├── metadata.json    # 自动抽取的元数据（案号/日期/当事人）
    └── tables/
        ├── page1_table0.md     # 表格 Markdown
        ├── page1_table0.html   # 表格 HTML（保留原始格式）
        └── ...
```

浏览器访问 `http://localhost:8000/output/` 可浏览所有 OCR 结果。

## 元数据抽取

`ocr/metadata.py` 的 `extract_metadata()` 自动识别：
- 键值对（`案号：XXX`）
- 文档类型（判决书/起诉书/裁定书/通知书/申报书...）
- 日期（`2024年1月15日` 格式）
- 人员信息（姓名+性别+年龄）

### 扩展方式

修改 `KEY_ALIASES` 字典即可适配新文档类型：
```python
KEY_ALIASES = {
    "案号": "case_number",
    "被告人": "defendant",
    # 新增你的字段映射...
}
```

## 已知问题与待优化

### 检测

- [ ] 混合型 PDF（部分页文字、部分页扫描件）目前按全文档级别判断，
      理想方案是逐页判断 + 混合处理
- [ ] 空白符阈值 15% 对极端情况可能需要调整

### OCR 质量

- [ ] 手写内容识别率低（PaddleOCR 主要针对印刷体）
- [ ] 竖排文字可能漏识别
- [ ] 印章/签名可能被识别为乱码（已通过 _SKIP_LABELS 过滤 seal 标签）

### 性能

- [ ] PP-StructureV3 模型首次加载 ~10s，后续复用（已做懒加载）
- [ ] 逐页串行处理，多页文档可考虑并行（但 PP-StructureV3 不支持 batch）
- [ ] 大文档（200+ 页）内存占用高，可考虑分批次处理 + 流式写入
- [ ] 上传接口目前同步等待 OCR 完成，大文档会导致 HTTP 超时
      → 后续可升级为异步任务模式（ThreadPoolExecutor + 轮询）
- [ ] MPS 加速在 PaddlePaddle 3.2.2 是实验性的，后续版本可能更稳定

### 功能

- [ ] 表格内容目前嵌入 document.md 正文，但表格的语义结构（行列关系）在
      chunk 时会被打散 → 可考虑每个表格作为独立 chunk，metadata 标注 type:table
- [ ] OCR 产出的 metadata.json（案号、当事人等）未进入检索系统
      → 可存入 docs.json 注册表，前端展示 + 作为检索过滤条件
- [ ] 同一文件名（仅大小写不同）的 PDF 会覆盖 OCR 输出目录

### 前端

- [ ] 扫描件上传后无处理进度显示（同步等待期间前端只显示 loading bar）
- [ ] 文档预览弹窗中表格渲染可进一步美化（复杂表格可能对齐不佳）

---

## 调试技巧

### 检测 PDF 类型
```bash
cd backend && source venv/bin/activate
python3 -c "
from ocr.engine import detect_pdf_type
print(detect_pdf_type('pdfs/your_file.pdf'))
"
```

### 查看 fitz 提取的文字（判断是否乱码）
```bash
python3 -c "
import fitz
doc = fitz.open('pdfs/your_file.pdf')
print(repr(doc[0].get_text()[:500]))
doc.close()
"
```

### 手动触发 OCR（不需要通过 API）
```bash
python3 -c "
from pathlib import Path
from ocr.engine import process_scanned_pdf
result = process_scanned_pdf('pdfs/your_file.pdf', Path('ocr_output/test'))
print(result)
"
```

### 清除旧数据
```bash
rm -rf backend/vectorstore/ backend/ocr_output/
```
