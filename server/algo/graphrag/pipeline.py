"""GraphRAG 检索增强问答主流程（v4：LLM实体抽取 + 多轮追问 + 路径推理 + 溯源 + 流式）。

    问题 →（大模型/规则）抽实体 → 实体链接(按度数排序) → 多跳子图召回
         → 路径推理 → 上下文+溯源 →（带多轮历史）LLM 生成
"""
import re

from algo.knowledge_graph.normalize import canonical


def candidate_terms(question):
    """规则版候选词（无 LLM key 时的兜底）。"""
    stop = ["请问", "什么", "怎么", "如何", "哪些", "有没有", "可能", "是什么",
            "的", "了", "吗", "呢", "啊", "和", "与", "及", "这个", "那个",
            "有", "是", "会", "能", "为", "在", "该", "要", "我", "你", "它", "他"]
    q = question
    for s in stop:
        q = q.replace(s, " ")
    raw = [t for t in re.split(r"[\s，。、？！,.?!；;：:]+", q) if len(t) >= 2]
    terms = set(raw)
    for t in raw:
        for L in (2, 3, 4):
            for i in range(len(t) - L + 1):
                terms.add(t[i:i + L])
    return list(terms)


def extract_entities(question, llm):
    """优先用大模型抽取问题实体；失败或无 key 时退回规则分词。"""
    if llm is not None and getattr(llm, "available", False):
        ents = llm.extract_query_entities(question)
        if ents:
            # 同时补充规则词，提升召回
            return list(dict.fromkeys(ents + candidate_terms(question)))
    return candidate_terms(question)


def retrieve(question, neo4j, llm=None, prev_entities=None):
    """检索：返回 (排序后命中实体, 三元组, 推理路径)。

    prev_entities: 上一轮命中的实体；当本轮问题过短/指代（如“它”）匹配为空时复用。
    """
    terms = extract_entities(question, llm)
    # 同时加入归一化后的别名形式（如 感冒→急性上呼吸道感染、流感→流行性感冒），提升命中率
    terms = list(dict.fromkeys(terms + [canonical(t) for t in terms]))
    matched = neo4j.match_entities(terms)
    if not matched and prev_entities:
        matched = neo4j.match_entities(prev_entities)
    names = [m["name"] for m in matched][:5]

    triples, seen = [], set()
    for name in names:
        for t in neo4j.neighbors(name, hops=2):
            key = (t["head"], t["relation"], t["tail"])
            if key not in seen:
                seen.add(key)
                triples.append(t)

    reasoning = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for p in neo4j.paths_between(names[i], names[j]):
                if p.get("nodes"):
                    reasoning.append(_fmt_path(p))
    return matched, triples, reasoning[:5]


def build_context(triples):
    lines, sources = [], set()
    for t in triples:
        lines.append(f"({t['head']})-[{t['relation']}]->({t['tail']})")
        if t.get("source"):
            sources.add(t["source"])
    ctx = "\n".join(lines)
    if sources:
        ctx += "\n\n知识来源文档：" + "、".join(sorted(sources))
    return ctx


def graphrag_answer(question, llm, neo4j, history=None, prev_entities=None):
    matched, triples, reasoning = retrieve(question, neo4j, llm, prev_entities)
    names = [m["name"] for m in matched][:5]
    if not triples:
        # 图谱无命中：大模型可用则自由对话（打招呼/闲聊/通用问答），否则给提示
        if llm.available:
            try:
                text = llm.chat_freeform(question, history=history)
                return {"answer": text, "entities": [], "entityDetails": [], "triples": [],
                        "reasoning": [], "citations": [], "tripleCount": 0, "used_llm": True}
            except Exception:
                pass
        return _empty(names)
    context = build_context(triples)
    if llm.available:
        try:
            text = llm.answer(question, context, history=history)
            used = True
        except Exception as e:
            text = _template(names, triples) + f"\n\n(大模型调用失败：{e})"
            used = False
    else:
        text = _template(names, triples)
        used = False
    return _pack(text, matched, triples, reasoning, used)


def retrieve_for_stream(question, llm, neo4j, prev_entities=None):
    matched, triples, reasoning = retrieve(question, neo4j, llm, prev_entities)
    context = build_context(triples) if triples else ""
    meta = _pack("", matched, triples, reasoning, llm.available and bool(triples))
    return context, meta


# ---------- 辅助 ----------
def _fmt_path(p):
    nodes, rels = p["nodes"], p["rels"]
    parts = [nodes[0]]
    for i, rel in enumerate(rels):
        parts.append(f"--[{rel}]-->")
        parts.append(nodes[i + 1])
    return " ".join(parts)


def _pack(text, matched, triples, reasoning, used):
    citations = sorted({t["source"] for t in triples if t.get("source")})
    return {"answer": text, "entities": [m["name"] for m in matched][:8],
            "entityDetails": matched[:8], "triples": triples[:50],
            "reasoning": reasoning, "citations": citations,
            "tripleCount": len(triples), "used_llm": used}


def _empty(names):
    return {"answer": "未能在知识图谱中检索到相关知识点。可上传相关医疗文档并在"
                      "「知识图谱管理」中重建图谱后再试。",
            "entities": names, "entityDetails": [], "triples": [],
            "reasoning": [], "citations": [], "tripleCount": 0, "used_llm": False}


def _template(names, triples):
    lines = [f"根据知识图谱中与「{('、'.join(names)) or '相关实体'}」有关的信息："]
    grouped = {}
    for t in triples:
        grouped.setdefault(t["relation"], [])
        if t["tail"] not in grouped[t["relation"]]:
            grouped[t["relation"]].append(t["tail"])
    for rel, tails in grouped.items():
        lines.append(f"  · {rel}：{'、'.join(tails[:12])}")
    lines.append("\n本回答仅供健康科普参考，不能替代执业医师的诊断与治疗。")
    return "\n".join(lines)
