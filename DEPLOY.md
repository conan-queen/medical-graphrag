# 部署手册 · 阿里云 / 腾讯云（Docker Compose 一键部署）

本手册把「医脉 GraphRAG 系统」部署到国内云服务器，对外提供访问。
架构：`Nginx(80/443) → 后端 gunicorn(5010) → Neo4j(内网)`，外加 SQLite 持久化卷。

---

## 一、准备工作

1. **买一台云服务器 ECS / CVM**
   - 配置建议 **2核4G 起**（Neo4j 比较吃内存；并发大再升）。
   - 系统选 **Ubuntu 22.04** 或 Anolis/AlmaLinux 均可。
   - 计费：按量或包月都行，先按量试。

2. **安全组（防火墙）只放行 Web 端口**
   - 放行入方向：**80**（HTTP）、**443**（HTTPS，配证书后用）。
   - **千万不要**对公网放行 5010 / 7687 / 7474（后端和 Neo4j 只走容器内网）。
   - SSH 端口 22 按需放行（建议限制来源 IP）。

3. **域名 + ICP 备案（合规必需）**
   - 在国内服务器上用域名对公众提供网站，**法律要求先做 ICP 备案**，否则会被关停。
   - 在阿里云/腾讯云控制台提交备案，通常几天到两周。备案期间可先用公网 IP 自测。

---

## 二、安装 Docker

```bash
# Ubuntu
curl -fsSL https://get.docker.com | bash
sudo systemctl enable --now docker
# 验证
docker version && docker compose version
```

---

## 三、上传项目并配置

1. 把本项目文件夹整体上传到服务器（scp / 宝塔面板 / git 均可），例如放到 `/opt/medical-graphrag`。

2. 进入目录，复制并填写环境变量：
   ```bash
   cd /opt/medical-graphrag
   cp .env.example .env
   # 生成强随机 JWT 密钥
   echo "JWT_SECRET=$(openssl rand -hex 32)"
   ```
   用编辑器打开 `.env`，至少填好这三项：
   ```
   NEO4J_PASSWORD=你的强密码
   JWT_SECRET=上一步生成的随机串
   QWEN_API_KEY=百炼申请的key   # 留空则用内置示例演示
   ```

---

## 四、启动

```bash
docker compose up -d --build
```
- 首次会构建后端镜像、拉取 neo4j 和 nginx，耐心等几分钟。
- 查看状态与日志：
  ```bash
  docker compose ps
  docker compose logs -f backend
  ```
- 浏览器访问 `http://你的公网IP/`（或备案后的域名），应看到登录页。

> 健康检查：`http://你的公网IP/api/health` 返回 JSON 且 `neo4j:true` 即正常。

---

## 五、首次初始化数据

1. 用 **admin / 123456** 登录（**登录后立刻去「个人中心」改掉默认密码**，删除/禁用 test 账号）。
2. 进「知识库」→ 上传 `sample_docs/高血压科普.md` → 点「全量重建」→ 等进度条。
3. 回「智能问答」提问，验证检索与回答正常。

---

## 六、配 HTTPS（强烈建议）

方式一：阿里云/腾讯云**免费 SSL 证书**（控制台申请 → 下载 Nginx 格式 → 得到 `xxx.pem` 和 `xxx.key`）。

1. 把证书放到服务器，例如 `/opt/medical-graphrag/deploy/certs/`。
2. 在 `docker-compose.yml` 的 nginx 服务里放开 `443:443`，并挂载证书目录：
   ```yaml
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./frontend:/usr/share/nginx/html:ro
         - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
         - ./deploy/certs:/etc/nginx/certs:ro
   ```
3. 在 `deploy/nginx.conf` 增加一个 443 server 段（把 `server_name` 改成你的域名）：
   ```nginx
   server {
       listen 443 ssl;
       server_name yourdomain.com;
       ssl_certificate     /etc/nginx/certs/yourdomain.pem;
       ssl_certificate_key /etc/nginx/certs/yourdomain.key;
       client_max_body_size 20m;
       root /usr/share/nginx/html;
       index index.html;
       location / { try_files $uri $uri/ /index.html; }
       location /api/ {
           proxy_pass http://backend:5010;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header Connection '';
           proxy_buffering off; proxy_cache off; proxy_read_timeout 300s;
       }
   }
   # 80 端口自动跳转 443（可选）
   server { listen 80; server_name yourdomain.com; return 301 https://$host$request_uri; }
   ```
4. 重启：`docker compose restart nginx`。
5. 把 `.env` 的 `FRONTEND_ORIGIN` 设为 `https://yourdomain.com` 后 `docker compose up -d` 让 CORS 收紧。

---

## 七、日常运维

- **看日志**：`docker compose logs -f backend`
- **重启/更新**：改完代码 `docker compose up -d --build`
- **备份数据**（重要）：数据都在 Docker 卷里
  ```bash
  docker run --rm -v medical-graphrag_app_data:/d -v $PWD:/b alpine tar czf /b/app_data.tgz -C /d .
  docker run --rm -v medical-graphrag_neo4j_data:/d -v $PWD:/b alpine tar czf /b/neo4j_data.tgz -C /d .
  ```
- **改默认管理员密码**：登录后在个人中心改；或重置库后用新密码重新初始化。

---

## 八、用户多了之后的升级方向

当前为中小规模设计，访问量上来后按需升级：
- **SQLite → PostgreSQL/MySQL**：`server/db.py` 换连接即可（SQLite 写并发有限）。
- **建图任务与限流 → Redis**：当前任务进度存在后端内存，所以只能单 worker；接 Redis 后可多 worker 横向扩容（`gunicorn.conf.py` 调整 workers）。
- **大模型成本**：已对 `/api/qa/chat*` 与建图接口加了限流；可再加「相同问题缓存」省钱。
- **监控**：接阿里云云监控 / Prometheus，配置异常告警。

> 免责声明：本系统为技术演示/教学用途，对外服务时请确保每个回答都带有「仅供健康科普参考，不能替代执业医师诊断」的提示，并留意医疗信息服务的相关合规要求。
