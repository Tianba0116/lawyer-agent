"""自动从文档文本中抽取结构化元数据。

使用通用模式（键值对、中文日期、人员记录），无需为每种文档单独配置模板。
"""
import re


# 标签分类：携带可读文本内容的标签
_TEXT_LABELS = frozenset({
    "title", "text", "paragraph", "figure_title", "header", "footer",
    "reference", "list", "abstract", "content", "formula",
})

# 直接跳过的标签
_SKIP_LABELS = frozenset({
    "number", "seal", "figure", "chart", "equation", "footnote",
})

# 中文键到标准英文名的别名映射
KEY_ALIASES = {
    "申请项目名称": "title",
    "项目名称": "title",
    "申请者姓名": "applicant",
    "申请人": "applicant",
    "所在学院": "college",
    "学科代码及名称": "discipline_full",
    "拟申请经费额度": "funding",
    "项目起止年限": "duration",
    "案号": "case_number",
    "案由": "case_cause",
    "被告人": "defendant",
    "公诉机关": "prosecutor",
    "审判长": "judge",
    "法院": "court",
}

# 文档类型识别模式
_DOC_TYPE_PATTERNS = [
    (r"([一-龥]{2,10}(?:判决书|裁定书|决定书|起诉书|通知书|申报书|申请书|报告书|意见书|批复))", "doc_type"),
]


def extract_metadata(sections: list[tuple]) -> dict:
    """从结构化的文档区块中自动发现元数据。

    Args:
        sections: list of (page_num, region_type, text) tuples

    Returns:
        dict: 包含发现的键值对、文档类型、日期、人员信息等
    """
    meta = {}
    combined = "\n".join([t for _, _, t in sections])

    # --- 1. 泛型键值对发现 ---
    kv_pattern = re.compile(
        r"(?:^|\n)\s*"
        r"([一-龥][一-龥A-Za-z0-9/\s]{0,18}[一-龥A-Za-z0-9/)]"  # key
        r")\s*[：:]\s*"
        r"([^\n]{1,120})"  # value（单行）
    )
    seen_keys = set()
    for match in kv_pattern.finditer(combined):
        key = match.group(1).strip()
        value = match.group(2).strip()
        if len(key) < 2 or key in seen_keys:
            continue
        if any(p in key for p in ("。", "，", "、", "；", "的", "是", "在", "和", "与")):
            continue
        seen_keys.add(key)
        meta[key] = value

    # --- 2. 文档类型识别 ---
    for pattern, label in _DOC_TYPE_PATTERNS:
        m = re.search(pattern, combined)
        if m:
            meta[label] = m.group(1)
            break

    # --- 3. 日期提取 ---
    date_pattern = re.compile(
        r"((?:20|19)\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)"
    )
    dates = date_pattern.findall(combined)
    if dates:
        meta["date"] = dates[0].replace(" ", "")

    # --- 4. 人员信息提取 ---
    person_pattern = re.compile(
        r"([一-龥]{2,4})\s*[男女]\s*(\d{2,3})\s*(\d{4}级|博士|硕士|本科)?"
    )
    participants = []
    seen_names = set()
    for match in person_pattern.finditer(combined):
        name = match.group(1)
        if name in seen_names:
            continue
        if len(name) == 2 and name in ("男女", "性别", "年龄", "姓名", "年级", "联系电话"):
            continue
        seen_names.add(name)
        gender = "男" if "男" in match.group(0) else "女"
        info = {"name": name, "gender": gender}
        age_str = match.group(2)
        if age_str:
            info["age"] = int(age_str)
        grade = match.group(3)
        if grade:
            info["grade"] = grade
        participants.append(info)

    if participants:
        meta["participants"] = participants

    # --- 5. 键名标准化 ---
    for raw_key, std_key in KEY_ALIASES.items():
        if raw_key in meta:
            meta[std_key] = meta.pop(raw_key)

    return meta
