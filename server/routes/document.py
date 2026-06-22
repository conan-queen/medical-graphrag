"""文档模块路由 /api/document：上传、列表、删除。"""
import hashlib
from pathlib import Path

from flask import Blueprint, request, g

import config
from db import get_conn
from utils.response import ok, fail
from utils.jwt_util import token_required
from algo_context import llm
from algo.extract.text_extract import extract_text

bp = Blueprint("document", __name__, url_prefix="/api/document")

ALLOWED = {".txt", ".md", ".pdf", ".docx"}


@bp.post("/upload")
@token_required
def upload():
    f = request.files.get("file")
    if not f:
        return fail("未接收到文件")
    suffix = Path(f.filename).suffix.lower()
    if suffix not in ALLOWED:
        return fail(f"暂不支持的格式：{suffix}（支持 txt/md/pdf/docx）")
    content = f.read()
    md5 = hashlib.md5(content).hexdigest()
    save_path = config.UPLOAD_DIR / f"{md5}{suffix}"
    save_path.write_bytes(content)
    with get_conn() as conn:
        exist = conn.execute("SELECT id FROM document WHERE file_md5=?", (md5,)).fetchone()
        if exist:
            return ok({"id": exist["id"], "duplicated": True}, "文档已存在（MD5去重）")
        summary = ""
        try:
            text = extract_text(str(save_path))
            summary = llm.summarize(text) if text.strip() else ""
        except Exception:
            summary = ""
        cur = conn.execute(
            "INSERT INTO document(user_id,name,file_path,file_md5,summary,is_graph_built) "
            "VALUES (?,?,?,?,?,0)",
            (g.user_id, f.filename, str(save_path), md5, summary),
        )
        return ok({"id": cur.lastrowid, "summary": summary},
                  "上传成功，请到知识库与建图中构建图谱")


@bp.get("/list")
@token_required
def list_docs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,name,summary,is_graph_built,create_time FROM document "
            "ORDER BY create_time DESC").fetchall()
    return ok([{
        "id": r["id"], "name": r["name"], "summary": r["summary"],
        "isGraphBuilt": r["is_graph_built"], "createTime": r["create_time"],
    } for r in rows])


@bp.delete("/<int:doc_id>")
@token_required
def delete_doc(doc_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM document WHERE id=?", (doc_id,))
    return ok(msg="删除成功")
