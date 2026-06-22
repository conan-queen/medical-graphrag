"""疾病知识 /api/product-info 与诊断记录 /api/production-record（含 CRUD + 图片）。"""
import hashlib
import json
from pathlib import Path

from flask import Blueprint, request, send_file

import config
from db import get_conn
from utils.response import ok, fail
from utils.jwt_util import token_required, admin_required

bp = Blueprint("product_info", __name__)

IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _save_image(f):
    suffix = Path(f.filename).suffix.lower()
    if suffix not in IMG_EXT:
        return None
    data = f.read()
    name = hashlib.md5(data).hexdigest() + suffix
    (config.UPLOAD_DIR / name).write_bytes(data)
    return name


# ---------------- 文件服务 ----------------
@bp.get("/api/file/<name>")
def get_file(name):
    p = config.UPLOAD_DIR / name
    if not p.exists():
        return fail("文件不存在", 404)
    return send_file(p)


# ---------------- 疾病知识 ----------------
@bp.get("/api/product-info/list")
@token_required
def disease_list():
    kw = request.args.get("keyword", "")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM product_info WHERE name LIKE ? OR product_code LIKE ? ORDER BY id",
            (f"%{kw}%", f"%{kw}%")).fetchall()
    return ok([dict(r) for r in rows])


@bp.post("/api/product-info")
@admin_required
def disease_create():
    d = request.get_json(force=True) or {}
    if not d.get("name"):
        return fail("疾病名称不能为空")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO product_info(product_code,name,cause,diagnosis_path,diagnosis_standard) "
            "VALUES (?,?,?,?,?)",
            (d.get("productCode"), d["name"], d.get("cause"),
             d.get("diagnosisPath"), d.get("diagnosisStandard")))
        return ok({"id": cur.lastrowid}, "新增成功")


@bp.put("/api/product-info/<int:pid>")
@admin_required
def disease_update(pid):
    d = request.get_json(force=True) or {}
    with get_conn() as conn:
        conn.execute(
            "UPDATE product_info SET product_code=?,name=?,cause=?,diagnosis_path=?,"
            "diagnosis_standard=? WHERE id=?",
            (d.get("productCode"), d.get("name"), d.get("cause"),
             d.get("diagnosisPath"), d.get("diagnosisStandard"), pid))
    return ok(msg="已更新")


@bp.post("/api/product-info/<int:pid>/image")
@admin_required
def disease_image(pid):
    f = request.files.get("image")
    if not f:
        return fail("未接收到图片")
    name = _save_image(f)
    if not name:
        return fail("图片格式不支持")
    with get_conn() as conn:
        conn.execute("UPDATE product_info SET image_path=? WHERE id=?", (name, pid))
    return ok({"image": name}, "图片已上传")


@bp.delete("/api/product-info/<int:pid>")
@admin_required
def disease_delete(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM production_record WHERE product_id=?", (pid,))
        conn.execute("DELETE FROM product_info WHERE id=?", (pid,))
    return ok(msg="删除成功")


# ---------------- 诊断记录 ----------------
@bp.get("/api/production-record/list")
@token_required
def record_list():
    pid = request.args.get("productId")
    with get_conn() as conn:
        if pid:
            rows = conn.execute(
                "SELECT r.*, p.name AS disease_name FROM production_record r "
                "LEFT JOIN product_info p ON r.product_id=p.id WHERE r.product_id=? ORDER BY r.id DESC",
                (pid,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT r.*, p.name AS disease_name FROM production_record r "
                "LEFT JOIN product_info p ON r.product_id=p.id ORDER BY r.id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["images"] = json.loads(d["images"]) if d.get("images") else []
        out.append(d)
    return ok(out)


@bp.post("/api/production-record")
@admin_required
def record_create():
    d = request.get_json(force=True) or {}
    if not d.get("productId"):
        return fail("必须关联疾病")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO production_record(product_id,batch_number,production_line,status,doctor,note) "
            "VALUES (?,?,?,?,?,?)",
            (d["productId"], d.get("batchNumber"), d.get("productionLine"),
             d.get("status"), d.get("doctor"), d.get("note")))
        return ok({"id": cur.lastrowid}, "新增成功")


@bp.put("/api/production-record/<int:rid>")
@admin_required
def record_update(rid):
    d = request.get_json(force=True) or {}
    with get_conn() as conn:
        conn.execute(
            "UPDATE production_record SET batch_number=?,production_line=?,status=?,doctor=?,note=? WHERE id=?",
            (d.get("batchNumber"), d.get("productionLine"), d.get("status"),
             d.get("doctor"), d.get("note"), rid))
    return ok(msg="已更新")


@bp.post("/api/production-record/<int:rid>/images")
@admin_required
def record_images(rid):
    files = request.files.getlist("images")
    if not files:
        return fail("未接收到图片")
    with get_conn() as conn:
        row = conn.execute("SELECT images FROM production_record WHERE id=?", (rid,)).fetchone()
        existing = json.loads(row["images"]) if row and row["images"] else []
        for f in files:
            name = _save_image(f)
            if name:
                existing.append(name)
        conn.execute("UPDATE production_record SET images=? WHERE id=?",
                     (json.dumps(existing), rid))
    return ok({"images": existing}, f"已上传 {len(files)} 张图片")


@bp.delete("/api/production-record/<int:rid>")
@admin_required
def record_delete(rid):
    with get_conn() as conn:
        conn.execute("DELETE FROM production_record WHERE id=?", (rid,))
    return ok(msg="删除成功")


# ---------------- 管理端统计 ----------------
@bp.get("/api/stats/overview")
@admin_required
def overview():
    with get_conn() as conn:
        def c(t):
            return conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        return ok({"userCount": c("user"), "documentCount": c("document"),
                   "conversationCount": c("conversation"), "qaCount": c("qa_history"),
                   "diseaseCount": c("product_info"), "recordCount": c("production_record")})
