# 医脉 · GraphRAG 医疗健康知识诊断系统（v3 · 产品级）

> 本版新增：多轮对话上下文、大模型抽问题实体+实体归一化去重、疾病/诊断记录完整CRUD与多图上传、多线程并发建图。

按参考项目（羊羊小栈）公开文档披露的真实架构从零编写，并在 GraphRAG 质量与产品体验上**做了超越**的开源实现。
不是原作者付费源码（其完整代码未公开）；技术栈、数据模型、API 约定全部对齐，并额外增强。

```
前端(Vue3 单文件) ──► Flask 后端:5010 ──► Neo4j:7687  知识图谱
                          ├─ SQLite  用户/文档/会话/问答/疾病/诊断记录
                          └─ 通义千问  三元组抽取 + 流式问答 + 摘要/关键词
```

## 相比付费完整版，本版「超越」的地方

| 能力 | 说明 |
|------|------|
| **流式回答 (SSE)** | 打字机式逐字输出，体验接近 ChatGPT |
| **答案可溯源** | 每次回答标注用到的图谱三元组与来源文档，点实体可在图中聚焦 |
| **推理链路可视化** | 展示实体间最短关系路径（多跳推理），点开即看「为什么这么答」 |
| **实体链接排序** | 命中实体按图中度数排序，优先围绕核心实体检索 |
| **异步建图 + 进度条** | 后台任务建图，前端轮询实时进度 |
| **文档 AI 摘要 + 关键词** | 上传即用大模型生成摘要 |
| **会话自动标题** | 首次提问由大模型生成会话标题 |
| **导出 Word** | 一键导出问答记录为 .docx |
| **图谱浏览器** | 类型过滤 / 节点搜索 / 力导向↔环形布局切换 / 度数决定节点大小 / 双击展开邻居 |
| **数据看板** | 实体类型分布饼图 + 关系 Top10 柱状图（ECharts） |

> 无 LLM key 也能完整演示：建图用内置示例三元组，问答退化为图谱模板（仍带溯源/推理）。

## 对齐参考项目的部分
Flask + SQLite + JWT(角色0/1) 后端，端口 5010，响应 `{code,msg,data}`，默认 `admin/123456`、`test/123456`；
Neo4j(密码 `neo4j123`)；通义千问(OpenAI 兼容/百炼)；7 张同名表；文档→LLM三元组→Neo4j 的 GraphRAG 建图。

## 目录
```
mgr-v3/
├── server/
│   ├── app.py / config.py / db.py / algo_context.py
│   ├── utils/        response · security(MD5) · jwt_util
│   ├── routes/       user · document · knowledge_graph · qa · product_info
│   └── algo/
│       ├── llm/              通义千问(三元组/流式问答/摘要/关键词/标题)
│       ├── knowledge_graph/  Neo4j客户端 · 建图器 · 异步任务 · 种子三元组
│       ├── extract/          文档文本抽取
│       └── graphrag/         检索增强主流程(实体链接/路径推理/溯源/流式)
├── frontend/index.html       Vue3 + ECharts + marked（免构建）
├── sample_docs/高血压科普.md
└── requirements.txt / .env.example
```

## 运行
```bash
# 1) Neo4j（密码与 .env 一致）
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/neo4j123 neo4j:5

# 2) 配置 + 依赖
cp .env.example .env          # 填 Neo4j 密码；可选填通义千问 QWEN_API_KEY
pip install -r requirements.txt

# 3) 后端（首次自动建库建表+种子）
cd server && python app.py    # http://127.0.0.1:5010

# 4) 前端：浏览器打开 frontend/index.html，用 admin / 123456 登录
```
通义千问 key 申请：阿里云百炼 https://bailian.console.aliyun.com/ 。

## 体验路径
登录 → 知识库 → 上传 `sample_docs/高血压科普.md` → 全量重建（看进度条）→
智能问答 → 问「高血压有哪些症状？该怎么治疗？」→ 看流式回答 + 命中实体 + 推理链路 + 右侧检索子图 →
点实体跳到「图谱浏览器」→ 试类型过滤/布局切换 → 「数据看板」看统计图表 → 「导出 Word」。

## 主要接口
```
POST /api/user/login | /register ; GET /api/user/current ; POST /api/user/password
POST /api/document/upload ; GET /api/document/list ; DELETE /api/document/<id>
POST /api/knowledge-graph/build/full | /build/incremental   (管理员, 异步, 返回taskId)
GET  /api/knowledge-graph/task/<tid>     建图进度
GET  /api/knowledge-graph/visualize?name=&types=   子图/全图
GET  /api/knowledge-graph/search?keyword=          节点搜索
GET  /api/knowledge-graph/stats                    图谱统计
POST /api/qa/chat            非流式问答
POST /api/qa/chat/stream     流式问答 (SSE: meta/delta/done)
GET  /api/qa/conversation/list ; POST /api/qa/conversation ; DELETE .../<id>
GET  /api/qa/history/<cid> ; GET /api/qa/export/<cid>   导出Word
GET  /api/product-info/list ; GET /api/stats/overview (管理员)
```

## 再进一步可扩展
qwen-vl 传图识别、文档目录树、诊断记录多图上传、向量召回与图召回混合(Hybrid RAG)、把单文件前端拆成正式 Vite+TS+Element Plus 工程。需要哪块说一声。

> 免责声明：技术演示/教学用途，输出仅供健康科普参考，不能替代执业医师诊断与治疗。
