FROM python:3.11-slim

# 用国内 pip 镜像加速（阿里云/腾讯云上构建更快）
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ /app/server/
COPY sample_docs/ /app/sample_docs/

WORKDIR /app/server
EXPOSE 5010
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
