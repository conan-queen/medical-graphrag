"""用户模块路由 /api/user（对齐参考项目接口约定）。"""
from flask import Blueprint, request, g

from db import get_conn
from utils.response import ok, fail
from utils.security import hash_password, verify_password
from utils.jwt_util import create_token, token_required, admin_required

bp = Blueprint("user", __name__, url_prefix="/api/user")


def _to_info(row):
    return {
        "id": row["id"], "username": row["username"], "realName": row["real_name"],
        "phone": row["phone"], "email": row["email"], "role": row["role"],
        "status": row["status"], "createTime": row["create_time"],
        "updateTime": row["update_time"],
    }


@bp.post("/login")
def login():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return fail("用户名或密码不能为空")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user WHERE username=?", (username,)).fetchone()
    if not row or not verify_password(password, row["password"]):
        return fail("用户名或密码错误")
    if row["status"] != 1:
        return fail("账号已被禁用")
    token = create_token(row["id"], row["role"])
    return ok({"userInfo": _to_info(row), "token": token}, "登录成功")


@bp.post("/register")
def register():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return fail("用户名或密码不能为空")
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM user WHERE username=?", (username,)).fetchone():
            return fail("用户名已存在")
        conn.execute(
            "INSERT INTO user(username,password,real_name,phone,email,role,status) "
            "VALUES (?,?,?,?,?,0,1)",
            (username, hash_password(password), data.get("realName"),
             data.get("phone"), data.get("email")),
        )
    return ok(msg="注册成功")


@bp.get("/current")
@token_required
def current():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user WHERE id=?", (g.user_id,)).fetchone()
    return ok(_to_info(row)) if row else fail("用户不存在", 404)


@bp.post("/password")
@token_required
def change_password():
    data = request.get_json(force=True) or {}
    old, new = data.get("oldPassword") or "", data.get("newPassword") or ""
    with get_conn() as conn:
        row = conn.execute("SELECT password FROM user WHERE id=?", (g.user_id,)).fetchone()
        if not row or not verify_password(old, row["password"]):
            return fail("原密码错误")
        conn.execute("UPDATE user SET password=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
                     (hash_password(new), g.user_id))
    return ok(msg="密码修改成功")


# ==================== 管理员：用户管理 ====================
@bp.get("/page")
@admin_required
def user_page():
    current = int(request.args.get("current", 1))
    size = int(request.args.get("size", 10))
    username = request.args.get("username", "")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM user WHERE username LIKE ? ORDER BY id LIMIT ? OFFSET ?",
            (f"%{username}%", size, (current - 1) * size)).fetchall()
        total = conn.execute("SELECT COUNT(*) c FROM user WHERE username LIKE ?",
                             (f"%{username}%",)).fetchone()["c"]
    return ok({"records": [_to_info(r) for r in rows], "total": total,
               "current": current, "size": size})


@bp.put("/<int:uid>/status")
@admin_required
def update_status(uid):
    status = (request.get_json(force=True) or {}).get("status", 1)
    with get_conn() as conn:
        conn.execute("UPDATE user SET status=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
                     (status, uid))
    return ok(msg="状态已更新")


@bp.put("/<int:uid>/reset-password")
@admin_required
def reset_password(uid):
    with get_conn() as conn:
        conn.execute("UPDATE user SET password=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
                     (hash_password("123456"), uid))
    return ok(msg="密码已重置为 123456")


@bp.delete("/<int:uid>")
@admin_required
def delete_user(uid):
    if uid == g.user_id:
        return fail("不能删除当前登录的管理员")
    with get_conn() as conn:
        conn.execute("DELETE FROM user WHERE id=?", (uid,))
    return ok(msg="用户已删除")
