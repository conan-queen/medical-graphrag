"""知识图谱模块路由 /api/knowledge-graph（v3：异步建图 + 进度 + 搜索）。"""
from flask import Blueprint, request

from db import get_conn
from utils.response import ok, fail
from utils.jwt_util import admin_required, token_required
from algo_context import llm, neo4j
from algo.extract.text_extract import extract_text
from algo.knowledge_graph.builder import build_from_text
from algo.knowledge_graph import tasks

bp = Blueprint("kg", __name__, url_prefix="/api/knowledge-graph")


def _start_build(full):
    if not neo4j.ping():
        return fail("Neo4j 连接失败，请检查图数据库是否启动及密码配置", 500)
    with get_conn() as conn:
        sql = "SELECT * FROM document" if full else \
              "SELECT * FROM document WHERE is_graph_built=0"
        docs = [dict(r) for r in conn.execute(sql).fetchall()]

    tid = tasks.new_task(total=max(len(docs), 1))

    def job():
        try:
            if full:
                neo4j.clear()
            total = 0
            if not docs:
                n = build_from_text("", llm, neo4j, source="seed")
                tasks.update(tid, done=1, triples=n, message="无文档，已写入内置示例图谱")
                tasks.finish(tid, n, "已写入内置示例图谱")
                return
            for i, d in enumerate(docs):
                tasks.update(tid, message=f"正在处理：{d['name']}")
                text = extract_text(d["file_path"]) if d["file_path"] else ""
                n = build_from_text(text, llm, neo4j, source=d["name"])
                total += n
                with get_conn() as c:
                    c.execute("UPDATE document SET is_graph_built=1 WHERE id=?", (d["id"],))
                tasks.update(tid, done=i + 1, triples=total)
            tasks.finish(tid, total, f"构建完成，共写入三元组 {total} 条")
        except Exception as e:
            tasks.fail(tid, f"构建失败：{e}")

    tasks.run_async(job)
    return ok({"taskId": tid}, "构建任务已启动")


@bp.post("/build/full")
@admin_required
def build_full():
    return _start_build(True)


@bp.post("/build/incremental")
@admin_required
def build_incremental():
    return _start_build(False)


@bp.get("/task/<tid>")
@token_required
def task_status(tid):
    t = tasks.get(tid)
    return ok(t) if t else fail("任务不存在", 404)


@bp.get("/visualize")
@token_required
def visualize():
    name = request.args.get("name")
    types = request.args.get("types")
    type_filter = types.split(",") if types else None
    return ok(neo4j.subgraph(name=name, type_filter=type_filter))


@bp.get("/search")
@token_required
def search():
    kw = request.args.get("keyword", "").strip()
    if not kw:
        return ok([])
    return ok(neo4j.search_nodes(kw))


@bp.get("/stats")
@token_required
def stats():
    if not neo4j.ping():
        return fail("Neo4j 未连接", 500)
    return ok(neo4j.stats())
