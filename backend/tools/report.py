from langchain_core.tools import tool
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from core.config import config


@tool
def generate_report_tool(conversation_summary: str, file_name: str = "") -> str:
    """生成包含对话摘要的可下载 PDF 报告。

    Args:
        conversation_summary: 对话摘要，包括所有问答对。
        file_name: 文档名称。如果用户未上传文档，传空字符串。

    Returns:
        已保存报告的路径。
    """
    if not file_name:
        return "当前未上传任何文档，无法生成报告。请告知用户先上传一份法律 PDF 文档并进行对话。"

    c = canvas.Canvas(config.report_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "AI 法律助手 - 对话报告")
    c.setFont("Helvetica", 12)
    c.drawString(100, 730, f"文档：{file_name}")
    c.drawString(100, 715, "以下为您与 AI 法律助手的对话记录：")

    y = 685
    max_width = 450
    line_height = 15

    for line in conversation_summary.split("\n"):
        wrapped = simpleSplit(line, "Helvetica", 12, max_width)
        for w in wrapped:
            if y < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = 750
            c.drawString(100, y, w)
            y -= line_height
        y -= 5

    c.save()
    return f"报告已保存至 {config.report_path}"
