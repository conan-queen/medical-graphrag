"""密码安全：PBKDF2-HMAC-SHA256（带随机盐，标准库实现，无需额外依赖）。

存储格式：pbkdf2$<迭代次数>$<盐hex>$<摘要hex>
verify_password 同时兼容旧的 32 位 MD5（便于从演示库平滑迁移）。
"""
import hashlib
import hmac
import os

_ITER = 200_000


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iters, salt_hex, hash_hex = stored.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(iters))
            return hmac.compare_digest(dk.hex(), hash_hex)
        except Exception:
            return False
    # 兼容旧的 MD5 存量数据
    return hashlib.md5(pw.encode("utf-8")).hexdigest() == stored


def md5(text: str) -> str:  # 保留以兼容旧调用
    return hashlib.md5(text.encode("utf-8")).hexdigest()
