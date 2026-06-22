"""SQLite 数据层。

按参考项目《数据库开发文档》建 7 张核心表，并写入种子用户（admin/test）。
用户表字段严格对齐文档；其余表为对应业务设计的等价实现。
"""
import sqlite3
from contextlib import contextmanager

import config
from utils.security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    real_name VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    avatar_bucket VARCHAR(50),
    avatar_object_key VARCHAR(255),
    role INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_folder (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    folder_id INTEGER,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_md5 VARCHAR(64),
    summary TEXT,
    is_graph_built INTEGER NOT NULL DEFAULT 0,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) DEFAULT '新会话',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qa_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    entities TEXT,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code VARCHAR(50),
    name VARCHAR(100) NOT NULL,
    cause TEXT,
    diagnosis_path TEXT,
    diagnosis_standard TEXT,
    image_path VARCHAR(500),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    batch_number VARCHAR(50),
    production_line VARCHAR(100),
    status VARCHAR(50),
    note TEXT,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_role ON user(role);
CREATE INDEX IF NOT EXISTS idx_product_info_name ON product_info(name);
CREATE INDEX IF NOT EXISTS idx_qa_history_conversation_id ON qa_history(conversation_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        _seed(conn)


def _migrate(conn):
    """轻量迁移：为已存在的旧库补充新增列。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(production_record)")]
    if "images" not in cols:
        conn.execute("ALTER TABLE production_record ADD COLUMN images TEXT")
    cols2 = [r["name"] for r in conn.execute("PRAGMA table_info(production_record)")]
    if "doctor" not in cols2:
        conn.execute("ALTER TABLE production_record ADD COLUMN doctor VARCHAR(50)")


def _seed(conn):
    cur = conn.execute("SELECT COUNT(*) c FROM user")
    if cur.fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO user(username,password,real_name,role) VALUES (?,?,?,?)",
            [("admin", hash_password("123456"), "系统管理员", 1),
             ("test", hash_password("123456"), "测试用户", 0)],
        )
    cur = conn.execute("SELECT COUNT(*) c FROM product_info")
    if cur.fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO product_info(product_code,name,cause,diagnosis_path,diagnosis_standard) VALUES (?,?,?,?,?)",
            [("D001", "原发性高血压", "遗传、高钠饮食、超重等多因素",
              "诊室血压测量→动态血压监测→靶器官评估", "非同日三次SBP≥140或DBP≥90mmHg"),
             ("D002", "2型糖尿病", "胰岛素抵抗叠加肥胖、缺乏运动",
              "空腹血糖→OGTT→糖化血红蛋白", "空腹血糖≥7.0或OGTT 2h≥11.1mmol/L"),
             ("D003", "慢性胃炎", "幽门螺杆菌感染、饮食不规律",
              "胃镜检查→幽门螺杆菌检测", "胃镜下胃黏膜慢性炎症改变")],
        )
