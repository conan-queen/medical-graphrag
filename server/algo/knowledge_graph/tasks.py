"""异步建图任务管理（内存版）。

参考项目支持「图谱构建任务的进度查询」，这里用后台线程 + 内存任务表实现。
生产可换成 Celery / RQ；演示场景内存版足够。
"""
import threading
import uuid

_TASKS = {}
_LOCK = threading.Lock()


def new_task(total=0):
    tid = uuid.uuid4().hex[:12]
    with _LOCK:
        _TASKS[tid] = {"id": tid, "status": "running", "progress": 0,
                       "total": total, "done": 0, "triples": 0, "message": "开始构建"}
    return tid


def update(tid, **kw):
    with _LOCK:
        if tid in _TASKS:
            _TASKS[tid].update(kw)
            t = _TASKS[tid]
            if t["total"]:
                t["progress"] = int(t["done"] / t["total"] * 100)


def finish(tid, triples, message="构建完成"):
    with _LOCK:
        if tid in _TASKS:
            _TASKS[tid].update(status="success", progress=100,
                               triples=triples, message=message)


def fail(tid, message):
    with _LOCK:
        if tid in _TASKS:
            _TASKS[tid].update(status="failed", message=message)


def get(tid):
    with _LOCK:
        return dict(_TASKS.get(tid, {}))


def run_async(fn):
    threading.Thread(target=fn, daemon=True).start()
