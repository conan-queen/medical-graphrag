# gunicorn 生产配置
# 注意：本项目用了 SSE 流式 和 内存建图任务表，必须单 worker + 多线程。
# 要横向扩容（多 worker），需先把任务状态与限流改为 Redis 存储。
bind = "0.0.0.0:5010"
workers = 1
worker_class = "gthread"
threads = 8
timeout = 300          # 流式回答可能较长
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
