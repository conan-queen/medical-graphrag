"""后端主入口（Flask）。

- 本地开发：python app.py（读 config.DEBUG，默认关）
- 生产部署：gunicorn -c gunicorn.conf.py app:app（导入即完成建库）
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from flask import Flask
from flask_cors import CORS

import config
from db import init_db
from utils.response import ok
from algo_context import llm, neo4j

from routes.user import bp as user_bp
from routes.document import bp as doc_bp
from routes.knowledge_graph import bp as kg_bp
from routes.qa import bp as qa_bp
from routes.product_info import bp as pi_bp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

# CORS：配置了 FRONTEND_ORIGIN 则只放行这些来源；同域 Nginx 部署可不配
if config.FRONTEND_ORIGIN:
    CORS(app, origins=[o.strip() for o in config.FRONTEND_ORIGIN.split(",")],
         supports_credentials=True)
else:
    CORS(app)

for bp in (user_bp, doc_bp, kg_bp, qa_bp, pi_bp):
    app.register_blueprint(bp)

# 限流（保护大模型调用成本与防刷）。内存存储，适配单 worker；多 worker 需接 Redis
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(get_remote_address, app=app, default_limits=["240 per hour"],
                      storage_uri="memory://")
    for ep, rule in {"qa.chat": "30 per minute", "qa.chat_stream": "30 per minute",
                     "kg.build_full": "6 per minute", "kg.build_incremental": "12 per minute"}.items():
        if ep in app.view_functions:
            app.view_functions[ep] = limiter.limit(rule)(app.view_functions[ep])
except Exception as e:  # 未安装 flask-limiter 时跳过，不影响运行
    print("限流未启用:", e)


@app.get("/api/health")
def health():
    return ok({
        "backend": "ok",
        "neo4j": neo4j.ping(),
        "llmAvailable": llm.available,
        "model": __import__("algo.llm.config", fromlist=["QWEN_TEXT_MODEL"]).QWEN_TEXT_MODEL
        if llm.available else None,
    })


# 导入即初始化数据库（gunicorn 下也会执行；CREATE TABLE IF NOT EXISTS 幂等）
init_db()

if config.JWT_SECRET == "change-this-secret-in-prod":
    print("⚠️  警告：JWT_SECRET 仍为默认值，生产环境务必在环境变量中改成强随机值！")


if __name__ == "__main__":
    print("== 医疗 GraphRAG 后端 ==")
    print(f"端口      : http://127.0.0.1:{config.BACKEND_PORT}")
    print(f"Neo4j 连接: {neo4j.ping()}")
    print(f"LLM 可用  : {llm.available}")
    print(f"调试模式  : {config.DEBUG}")
    app.run(host="0.0.0.0", port=config.BACKEND_PORT, debug=config.DEBUG)
