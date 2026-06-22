"""Neo4j 配置。"""
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
import config as _root  # noqa

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")
