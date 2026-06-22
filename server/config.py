"""后端总配置（环境变量优先，便于容器化部署）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")  # 本地开发用；容器部署用环境变量注入

# 服务
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5010"))
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-prod")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
DEBUG = os.getenv("DEBUG", "0") == "1"

# 允许的前端来源（CORS）。同域 Nginx 部署可不填；多个用逗号分隔
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()

# 上传大小上限（字节），默认 20MB
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(20 * 1024 * 1024)))

# SQLite（可用环境变量指向持久化卷）
DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).resolve().parent / "yyxz_sqlite.db")))

# 上传目录（可用环境变量指向持久化卷）
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parent / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_DOCS = ROOT / "sample_docs"
