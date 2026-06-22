"""JWT 认证：签发/校验 token，提供 @token_required / @admin_required 装饰器。"""
import datetime
from functools import wraps

import jwt
from flask import request, g

import config
from utils.response import fail


def create_token(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def _decode():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], config.JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        payload = _decode()
        if not payload:
            return fail("未登录或登录已过期", code=401)
        g.user_id = payload["user_id"]
        g.role = payload["role"]
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        payload = _decode()
        if not payload:
            return fail("未登录或登录已过期", code=401)
        if payload.get("role") != 1:
            return fail("需要管理员权限", code=403)
        g.user_id = payload["user_id"]
        g.role = payload["role"]
        return fn(*args, **kwargs)
    return wrapper
