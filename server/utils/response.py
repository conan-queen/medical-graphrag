"""统一响应格式：{code, msg, data}（对齐参考项目接口约定）。"""
from flask import jsonify


def ok(data=None, msg="操作成功"):
    return jsonify({"code": 200, "msg": msg, "data": data})


def fail(msg="操作失败", code=400, data=None):
    return jsonify({"code": code, "msg": msg, "data": data}), code
