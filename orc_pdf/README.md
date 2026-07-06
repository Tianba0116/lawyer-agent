# OCR-KB — 扫描件PDF结构化提取工具

基于 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) PP-StructureV3 + PyMuPDF 的中文扫描件PDF提取工具。将扫描件/图片型PDF自动转为结构化Markdown，同时提取表格、元数据和人员信息，可直接作为RAG知识库的预处理管线。

## 特性

- **布局分析** — 自动识别标题、正文、表格、页眉页脚、公式等区域
- **表格重建** — 提取表格并输出 `.md` + `.html` 双格式
- **元数据抽取** — 自动发现 `字段：值` 模式，无需预设文档模板
- **文档类型识别** — 自动识别判决书、起诉书、申报书等常见公文类型
- **人员信息提取** — 自动识别姓名、性别、年龄、年级等信息
- **跨页合并** — 被页边界截断的段落自动拼接
- **去重去噪** — 过滤印章/签名等OCR噪声，去除重叠检测导致的重复文本

## 目录结构

```
├── ocr_extract.py          # 基础OCR：整页逐页文字提取
├── ocr_structure.py        # 结构化提取（推荐）：布局 + 表格 + 元数据
├── requirements.txt
├── .gitignore
└── README.md
```

## 环境要求

- Python 3.8+
- PaddlePaddle 3.2.x（3.3.x 存在 ONEDNN 兼容性问题）
- PaddleOCR ≥ 3.5.0
- PyMuPDF
- Pillow / NumPy

```bash
pip install paddlepaddle==3.2.2 paddleocr pymupdf pillow numpy paddlex[ocr]
```

## 使用方法

### 结构化提取（推荐）

```bash
python ocr_structure.py
```

默认读取当前目录下的 `input.pdf`，输出到 `output_kb/`：

```
output_kb/
├── document.md             # 完整结构化文档（按页组织、表格引用）
├── metadata.json           # 自动提取的元数据
└── tables/                 # 表格文件
    ├── page1_table0.md
    ├── page1_table0.html
    └── ...
```

如需修改输入文件，编辑脚本顶部的 `PDF_PATH` 和 `OUTPUT_DIR`。

### 基础OCR

```bash
python ocr_extract.py
```

整页逐页OCR，输出为带页码标题的 `output_ocr.md`。不进行布局分析和表格识别。

## 如何适配不同类型文档

`_extract_metadata` 函数无需为每种文档单独配置。它通过以下通用机制工作：

1. **键值对自动发现** — 匹配文本中所有 `字段名：值` 模式的键值对
2. **文档类型识别** — 检测标题中的 `XX判决书/起诉书/申报书/…` 后缀
3. **日期提取** — 匹配 `2024年1月1日` 格式
4. **人员识别** — 匹配 `姓名 性别 年龄 年级` 模式

如需定制 key 的别名映射（如 `案号→case_number`），修改 `KEY_ALIASES` 字典即可。

## 技术方案

```
PDF → PyMuPDF渲染(200DPI) → PP-StructureV3
                                  ├── Layout Detection (PP-DocLayout_plus-L)
                                  ├── OCR (PP-OCRv5_server)
                                  ├── Table Recognition (SLANeXt + RT-DETR-L)
                                  └── Formula Recognition (PP-FormulaNet_plus-L)
                                          ↓
                              结构化区块 + 表格HTML
                                          ↓
                              HTML→MD转换 + 元数据抽取
                                          ↓
                              output_kb/
```

## 适用场景

- 法院判决书、起诉书等法律文书的结构化入库
- 申报书、审批表等行政表单的批量提取
- 扫描版古籍/文献的数字化
- RAG知识库的PDF预处理管线

## License

MIT
