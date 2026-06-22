"""知识图谱构建器（GraphRAG 的「建图」环节）。

流程：文档文本 → 切分 → 【多线程并发】LLM 抽取三元组 → 实体归一化去重 → 写入 Neo4j。
无 LLM key 时回退到内置医疗种子三元组，保证流程可演示。
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from algo.extract.text_extract import extract_text
from algo.knowledge_graph.normalize import normalize_triples

SEED_FILE = Path(__file__).resolve().parent / "seed_triples.json"
MAX_WORKERS = 4


def _chunk(text, size=2500):
    text = text.replace("\r", "")
    return [text[i:i + size] for i in range(0, len(text), size)] or []


def build_from_text(text, llm, neo4j, source="manual", progress=None):
    """对一段文本抽取三元组并写入图谱，返回写入的三元组数。

    progress: 可选回调 progress(done, total)，用于上报分块进度。
    """
    total = []
    if llm.available and text.strip():
        chunks = _chunk(text)
        done = 0
        # 多线程并发抽取，加速建图（每个分块一次 LLM 调用）
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(llm.extract_triples, c): i for i, c in enumerate(chunks)}
            for fut in as_completed(futures):
                try:
                    total.extend(fut.result() or [])
                except Exception:
                    pass
                done += 1
                if progress:
                    progress(done, len(chunks))
    if not total:
        total = _load_seed()
        source = source + "(seed)"
    total = normalize_triples(total)          # 归一化 + 去重
    neo4j.add_triples(total, source_doc=source)
    return len(total)


def build_from_file(path, llm, neo4j, source=None, progress=None):
    text = extract_text(path)
    if not text.strip():
        return 0, "文档文本抽取为空（格式不支持或为扫描件/图片）"
    n = build_from_text(text, llm, neo4j, source=source or Path(path).name, progress=progress)
    return n, "ok"


def _load_seed():
    try:
        return json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
