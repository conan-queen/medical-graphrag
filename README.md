# 医脉 · 基于 GraphRAG 的医疗健康智能问答系统

> 融合大语言模型与医疗知识图谱（GraphRAG）的智能问答系统，让医疗回答既智能又**可溯源**。从需求设计到容器化部署上线，全流程独立完成。

通用大模型在医疗问答中容易“一本正经地胡说”，且回答缺乏依据、难以追溯。本项目采用 **GraphRAG 架构**：先用大模型从医疗文档抽取「实体—关系」三元组、构建 **Neo4j** 结构化知识图谱；问答时围绕用户问题做实体识别与「知识图谱 + 疾病库 + 历史诊断记录」**三路混合检索**，将命中的图谱关系作为上下文交给大模型生成回答。每个结论都能回溯到具体的图谱关系与来源文档，在保留大模型自然语言能力的同时，显著提升医疗回答的相关性与可解释性。

系统支持多轮对话、图文多模态问诊与知识图谱可视化，并已通过 Docker 容器化部署、可公网访问演示。

```
前端 (Vue3 单文件) ──► Flask 后端 :5010 ──► Neo4j :7687   医疗知识图谱
                            ├─ SQLite     用户 / 文档 / 会话 / 问答 / 疾病 / 诊断记录
                            └─ 通义千问    三元组抽取 + 流式问答 + 摘要 / 关键词
```

## ✨ 核心特性

| 能力 | 说明 |
|------|------|
| **GraphRAG 三路检索** | 知识图谱 (Top-7) + 疾病库 (Top-5) + 历史诊断记录 (Top-5) 混合召回，拼装上下文供模型生成 |
| **答案可溯源** | 每次回答标注用到的图谱三元组与来源文档，点实体可在图中聚焦 |
| **推理链路可视化** | 展示实体间最短关系路径（多跳推理），直观呈现「为什么这么答」 |
| **实体识别 + 归一化** | 大模型抽取问题实体并做同义词归一化去重，按图中度数排序优先围绕核心实体检索 |
| **流式回答 (SSE)** | 打字机式逐字输出，体验接近主流对话产品 |
| **图文多模态问诊** | 接入多模态模型，支持上传图片结合文本进行问诊 |
| **多轮对话上下文** | 历史消息 + 跨轮实体复用，支持连续追问 |
| **异步建图 + 进度条** | 后台任务建图，多线程并发抽取三元组，前端轮询实时进度 |
| **图谱浏览器** | 类型过滤 / 节点搜索 / 力导向↔环形布局切换 / 度数决定节点大小 / 双击展开邻居 |
| **数据看板** | 实体类型分布饼图 + 关系 Top10 柱状图（ECharts） |
| **文档与会话** | 文档上传建库、AI 摘要与关键词、会话自动标题、问答记录一键导出 Word |
| **管理后台** | 用户管理、疾病库与诊疗记录完整 CRUD 与多图上传 |

> 无大模型 Key 也能完整演示：建图使用内置示例三元组，问答退化为图谱模板（仍带溯源与推理链路）。

## 🧰 技术栈
- **后端**：Python 3.10 / Flask / Gunicorn，JWT 鉴权（角色 0/1），SQLite 业务库
- **知识图谱**：Neo4j 5.x
- **大模型**：通义千问（qwen-plus 文本 / qwen-vl 多模态，OpenAI 兼容接口）
- **前端**：Vue3 + ECharts + marked（单文件、免构建）
- **部署**：Docker Compose（Neo4j + Gunicorn + Nginx 三容器）

## 📁 目录结构
```
medical-graphrag/
├── server/
│   ├── app.py / config.py / db.py / algo_context.py
│   ├── utils/        response · security(MD5) · jwt_util
│   ├── routes/       user · document · knowledge_graph · qa · product_info
│   └── algo/
│       ├── llm/              大模型（三元组 / 流式问答 / 摘要 / 关键词 / 标题 / 多模态）
│       ├── knowledge_graph/  Neo4j 客户端 · 建图器 · 异步任务 · 种子三元组
│       ├── extract/          文档文本抽取
│       └── graphrag/         检索增强主流程（实体链接 / 路径推理 / 溯源 / 流式）
├── frontend/index.html       Vue3 + ECharts + marked（免构建）
├── sample_docs/高血压科普.md
├── deploy/nginx.conf
├── docker-compose.yml / Dockerfile / requirements.txt / .env.example
└── DEPLOY.md                 容器化部署说明
```

## 🚀 快速开始（本地）
```bash
# 1) 启动 Neo4j（密码需与 .env 一致，至少 8 位）
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4j123456 neo4j:5

# 2) 配置 + 依赖
cp .env.example .env          # 填 Neo4j 密码；可选填大模型 QWEN_API_KEY
pip install -r requirements.txt

# 3) 后端（首次自动建库建表 + 写入种子数据）
cd server && python app.py    # http://127.0.0.1:5010

# 4) 前端：浏览器打开 frontend/index.html，用 admin / 123456 登录
```

## 🐳 容器化部署
项目提供 Docker Compose 一键编排（Neo4j + Gunicorn 后端 + Nginx），详见 [`DEPLOY.md`](./DEPLOY.md)：
```bash
cp .env.example .env          # 配置密码、JWT 密钥、QWEN_API_KEY
docker compose up -d --build  # 启动后访问 http://服务器IP/
```

## 🧭 体验路径
登录 → 知识库 → 上传 `sample_docs/高血压科普.md` → 全量重建（看进度条）→
智能问答 → 问「高血压有哪些症状？该怎么治疗？」→ 看流式回答 + 命中实体 + 推理链路 + 右侧检索子图 →
点实体跳到「图谱浏览器」→ 试类型过滤 / 布局切换 → 「数据看板」看统计图表 → 「导出 Word」。

## 🔌 主要接口
```
POST /api/user/login | /register ; GET /api/user/current ; POST /api/user/password
POST /api/document/upload ; GET /api/document/list ; DELETE /api/document/<id>
POST /api/knowledge-graph/build/full | /build/incremental   (管理员, 异步, 返回 taskId)
GET  /api/knowledge-graph/task/<tid>     建图进度
GET  /api/knowledge-graph/visualize?name=&types=   子图 / 全图
GET  /api/knowledge-graph/search?keyword=          节点搜索
GET  /api/knowledge-graph/stats                    图谱统计
POST /api/qa/chat            非流式问答
POST /api/qa/chat/stream     流式问答 (SSE: meta / delta / done)
POST /api/qa/chat/image      图文多模态问答
GET  /api/qa/conversation/list ; POST /api/qa/conversation ; DELETE .../<id>
GET  /api/qa/history/<cid> ; GET /api/qa/export/<cid>   导出 Word
GET  /api/product-info/list ; GET /api/stats/overview (管理员)
```

## 🗺️ 后续规划
- 向量召回与图召回混合（Hybrid RAG）
- 文档目录树管理
- 域名 + HTTPS
- 将单文件前端拆为正式 Vite + TypeScript 工程

## 📄 License
[MIT](./LICENSE)

---

> **免责声明**：本项目为技术演示用途，输出仅供健康科普参考，不能替代执业医师的诊断与治疗。
