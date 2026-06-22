"""从上传文档中抽取纯文本（txt/md/pdf/docx）。

注：与参考系统一致，不抽取文档中的图片内容；部分格式异常的文件可能抽取失败。
"""
from pathlib import Path


def extract_text(path):
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            return p.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            return _pdf(p)
        if suffix in (".docx",):
            return _docx(p)
    except Exception as e:
        return f""  # 抽取失败返回空，调用方据此提示
    return ""


def _pdf(p):
    import pdfplumber
    parts = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx(p):
    import docx
    d = docx.Document(str(p))
    return "\n".join(par.text for par in d.paragraphs)
