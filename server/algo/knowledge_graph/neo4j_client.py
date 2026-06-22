"""Neo4j 图数据库客户端。

通用三元组图模式（适配 LLM 动态抽取）：
    节点: (:Entity {name, type})
    边:   (:Entity)-[:REL {name:"关系名", source:"来源文档"}]->(:Entity)
"""
from neo4j import GraphDatabase

from algo.knowledge_graph import config as cfg


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            cfg.NEO4J_URI, auth=(cfg.NEO4J_USER, cfg.NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def ping(self):
        try:
            with self.driver.session() as s:
                s.run("RETURN 1")
            return True
        except Exception:
            return False

    # ---------- 写入 ----------
    def clear(self):
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")

    def delete_by_source(self, source):
        with self.driver.session() as s:
            s.run("MATCH ()-[r:REL {source:$src}]->() DELETE r", src=source)
            s.run("MATCH (n:Entity) WHERE NOT (n)--() DELETE n")

    def add_triples(self, triples, source_doc=None):
        with self.driver.session() as s:
            for t in triples:
                if not t.get("head") or not t.get("tail") or not t.get("relation"):
                    continue
                s.run(
                    """MERGE (h:Entity {name:$h}) SET h.type=$ht
                       MERGE (t:Entity {name:$t}) SET t.type=$tt
                       MERGE (h)-[r:REL {name:$rel}]->(t)
                       SET r.source=$src""",
                    h=str(t["head"]).strip(), ht=t.get("head_type", "实体"),
                    t=str(t["tail"]).strip(), tt=t.get("tail_type", "实体"),
                    rel=str(t["relation"]).strip(), src=source_doc or "")

    # ---------- 检索（GraphRAG）----------
    def match_entities(self, names):
        if not names:
            return []
        with self.driver.session() as s:
            rows = s.run(
                """MATCH (e:Entity)
                   WHERE any(n IN $names WHERE e.name CONTAINS n OR n CONTAINS e.name)
                   OPTIONAL MATCH (e)-[r:REL]-()
                   RETURN e.name AS name, e.type AS type, count(r) AS degree
                   ORDER BY degree DESC LIMIT 20""", names=names)
            return [dict(r) for r in rows]

    def neighbors(self, name, hops=2, limit=60):
        with self.driver.session() as s:
            rows = s.run(
                f"""MATCH p=(e:Entity {{name:$name}})-[r:REL*1..{hops}]-(m:Entity)
                    WITH relationships(p) AS rels
                    UNWIND rels AS rel
                    WITH startNode(rel) AS a, rel, endNode(rel) AS b
                    RETURN DISTINCT a.name AS head, a.type AS head_type,
                           rel.name AS relation, b.name AS tail, b.type AS tail_type,
                           rel.source AS source
                    LIMIT {limit}""", name=name)
            return [dict(r) for r in rows]

    def paths_between(self, a, b, max_hops=3, limit=5):
        """两个实体间的最短关系路径（用于推理链路展示）。"""
        with self.driver.session() as s:
            rows = s.run(
                f"""MATCH p=shortestPath((x:Entity {{name:$a}})-[:REL*1..{max_hops}]-(y:Entity {{name:$b}}))
                    RETURN [n IN nodes(p) | n.name] AS nodes,
                           [r IN relationships(p) | r.name] AS rels LIMIT {limit}""",
                a=a, b=b)
            return [dict(r) for r in rows]

    # ---------- 可视化 / 搜索 / 统计 ----------
    def subgraph(self, name=None, type_filter=None, limit=150):
        with self.driver.session() as s:
            if name:
                rows = s.run(
                    """MATCH (c:Entity {name:$name})
                       MATCH (c)-[:REL*0..2]-(x:Entity)
                       WITH collect(DISTINCT x)+c AS ns
                       UNWIND ns AS a
                       MATCH (a)-[r:REL]->(b) WHERE b IN ns
                       RETURN DISTINCT a.name AS src, a.type AS src_type, r.name AS rel,
                              b.name AS dst, b.type AS dst_type LIMIT $limit""",
                    name=name, limit=limit)
            else:
                rows = s.run(
                    """MATCH (a:Entity)-[r:REL]->(b:Entity)
                       RETURN a.name AS src, a.type AS src_type, r.name AS rel,
                              b.name AS dst, b.type AS dst_type LIMIT $limit""",
                    limit=limit)
            g = self._to_graph([dict(r) for r in rows])
        if type_filter:
            keep = {n["id"] for n in g["nodes"] if n["type"] in type_filter}
            g["nodes"] = [n for n in g["nodes"] if n["id"] in keep]
            g["edges"] = [e for e in g["edges"]
                          if e["source"] in keep and e["target"] in keep]
        return self._with_degree(g)

    def search_nodes(self, keyword, limit=30):
        with self.driver.session() as s:
            rows = s.run(
                """MATCH (e:Entity) WHERE e.name CONTAINS $kw
                   OPTIONAL MATCH (e)-[r:REL]-()
                   RETURN e.name AS name, e.type AS type, count(r) AS degree
                   ORDER BY degree DESC LIMIT $limit""", kw=keyword, limit=limit)
            return [dict(r) for r in rows]

    @staticmethod
    def _to_graph(rows):
        nodes, edges, seen = [], [], set()
        for r in rows:
            for key, tkey in [("src", "src_type"), ("dst", "dst_type")]:
                nm = r[key]
                if nm not in seen:
                    seen.add(nm)
                    nodes.append({"id": nm, "name": nm, "type": r[tkey] or "实体"})
            edges.append({"source": r["src"], "target": r["dst"], "name": r["rel"]})
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _with_degree(g):
        deg = {}
        for e in g["edges"]:
            deg[e["source"]] = deg.get(e["source"], 0) + 1
            deg[e["target"]] = deg.get(e["target"], 0) + 1
        for n in g["nodes"]:
            n["degree"] = deg.get(n["id"], 0)
        return g

    def stats(self):
        with self.driver.session() as s:
            n = s.run("MATCH (n:Entity) RETURN count(n) AS c").single()["c"]
            e = s.run("MATCH ()-[r:REL]->() RETURN count(r) AS c").single()["c"]
            types = [dict(r) for r in s.run(
                "MATCH (n:Entity) RETURN n.type AS type, count(*) AS c ORDER BY c DESC")]
            rels = [dict(r) for r in s.run(
                "MATCH ()-[r:REL]->() RETURN r.name AS rel, count(*) AS c ORDER BY c DESC LIMIT 10")]
            return {"nodes": n, "edges": e, "types": types, "relations": rels}
