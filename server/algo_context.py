"""算法单例：全局共享的 Qwen 客户端与 Neo4j 客户端。"""
from algo.llm.client import QwenClient
from algo.knowledge_graph.neo4j_client import Neo4jClient

llm = QwenClient()
neo4j = Neo4jClient()
