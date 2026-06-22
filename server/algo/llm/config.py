"""大语言模型配置（通义千问 / 百炼 OpenAI 兼容）。"""
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
import config as _root  # noqa

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL",
                          "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus").strip()
QWEN_VL_MODEL = os.getenv("QWEN_VL_MODEL", "qwen-vl-plus").strip()
