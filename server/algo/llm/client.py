"""通义千问客户端（OpenAI 兼容接口）。

封装 GraphRAG 全流程所需的大模型能力：
  1) extract_triples : 文档→<头实体,关系,尾实体> 三元组（建图）
  2) answer / answer_stream : 基于图谱检索上下文生成回答（含流式）
  3) summarize / keywords : 文档 AI 摘要、关键词抽取
  4) gen_title : 会话自动标题
未配置 QWEN_API_KEY 时 available=False，调用方走降级逻辑。
"""
import json
import re

from algo.llm import config as cfg

TRIPLE_SYSTEM = (
    "你是医疗知识图谱构建助手。请从给定的医疗文本中抽取知识三元组，"
    "用于构建疾病、症状、病因、诊断步骤、治疗步骤、医疗设备、临床指标之间的关系。"
    "只输出 JSON 数组，每个元素形如 "
    '{"head":"头实体","head_type":"实体类型","relation":"关系","tail":"尾实体","tail_type":"实体类型"}。'
    "实体类型从 [疾病,症状,病因,诊断步骤,治疗步骤,医疗设备,临床指标,科室] 中选择。"
    "关系要简洁（如：常见症状/病因/诊断步骤/治疗步骤/使用设备/监测指标/就诊科室/并发症）。"
    "不要输出除 JSON 数组以外的任何文字。"
)

QA_SYSTEM = (
    "你是一名严谨的医疗健康知识助手。请【只依据】下面提供的「知识图谱检索结果」"
    "用中文回答用户问题，条理清晰、专业友好。涉及到具体事实时尽量对应到给出的三元组。"
    "若检索结果中没有相关信息，请如实说明知识库暂未收录，不要编造。"
    "回答结尾加一句：本回答仅供健康科普参考，不能替代执业医师的诊断与治疗。"
)

CHAT_SYSTEM = (
    "你是一个友好的医疗健康知识助手。"
    "如果用户是打招呼、寒暄或闲聊，请自然、简短、亲切地回应，并适当引导对方提出健康相关的问题。"
    "如果用户问的是医疗健康问题，但本系统知识库中暂无相关图谱数据，可基于通用医学常识简要回答，"
    "但要明确说明这部分内容不在本系统知识库中、仅供参考，并建议补充相关文档或咨询执业医师。"
    "重要：本系统【支持】图片识别，用户可点击输入框左下角的『上传图片』按钮上传医学相关图片。"
    "若用户提到图片/照片但本次消息没有附带图片，请友好提示对方点『上传图片』按钮把图片连同问题一起发送，"
    "绝对不要声称系统不支持图像功能、也不要说自己无法看图。"
    "用简洁的中文回答。"
)


class QwenClient:
    def __init__(self):
        self.available = bool(cfg.QWEN_API_KEY)
        self.client = None
        if self.available:
            from openai import OpenAI
            self.client = OpenAI(api_key=cfg.QWEN_API_KEY, base_url=cfg.QWEN_BASE_URL)

    def _chat(self, system, user, model=None, temperature=0.2):
        resp = self.client.chat.completions.create(
            model=model or cfg.QWEN_TEXT_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()

    def _chat_stream(self, system, user, model=None):
        stream = self.client.chat.completions.create(
            model=model or cfg.QWEN_TEXT_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.2, stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # ---------- 建图 ----------
    def extract_triples(self, text):
        if not self.available:
            return []
        raw = self._chat(TRIPLE_SYSTEM, f"医疗文本：\n{text[:6000]}")
        return _safe_json_array(raw)

    # ---------- 问答 ----------
    def answer(self, question, context, history=None):
        msgs = [{"role": "system", "content": QA_SYSTEM}]
        msgs += (history or [])
        msgs.append({"role": "user",
                     "content": f"用户问题：{question}\n\n知识图谱检索结果：\n{context}"})
        resp = self.client.chat.completions.create(
            model=cfg.QWEN_TEXT_MODEL, messages=msgs, temperature=0.2)
        return resp.choices[0].message.content.strip()

    def answer_stream(self, question, context, history=None):
        msgs = [{"role": "system", "content": QA_SYSTEM}]
        msgs += (history or [])
        msgs.append({"role": "user",
                     "content": f"用户问题：{question}\n\n知识图谱检索结果：\n{context}"})
        stream = self.client.chat.completions.create(
            model=cfg.QWEN_TEXT_MODEL, messages=msgs, temperature=0.2, stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def extract_query_entities(self, question):
        """用大模型从用户问题中抽取关键医疗实体（检索更准）。无 key 返回 []。"""
        if not self.available:
            return []
        try:
            raw = self._chat(
                "从用户的医疗问题中抽取关键实体（疾病/症状/检查/药物/科室等），"
                "只输出 JSON 字符串数组，最多6个，不要解释。", question, temperature=0.0)
            return [x for x in _safe_json_array(raw) if isinstance(x, str)][:6]
        except Exception:
            return []

    def chat_freeform(self, question, history=None):
        """图谱无命中时的自由对话：打招呼/闲聊/通用问答（非流式）。"""
        msgs = [{"role": "system", "content": CHAT_SYSTEM}] + (history or [])
        msgs.append({"role": "user", "content": question})
        resp = self.client.chat.completions.create(
            model=cfg.QWEN_TEXT_MODEL, messages=msgs, temperature=0.4)
        return resp.choices[0].message.content.strip()

    def chat_freeform_stream(self, question, history=None):
        """图谱无命中时的自由对话（流式）。"""
        msgs = [{"role": "system", "content": CHAT_SYSTEM}] + (history or [])
        msgs.append({"role": "user", "content": question})
        stream = self.client.chat.completions.create(
            model=cfg.QWEN_TEXT_MODEL, messages=msgs, temperature=0.4, stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def answer_with_image(self, question, image_b64, mime="image/jpeg", context=""):
        """多模态问答（qwen-vl）：结合上传的疾病图片与图谱上下文作答。"""
        resp = self.client.chat.completions.create(
            model=cfg.QWEN_VL_MODEL,
            messages=[{"role": "system", "content": QA_SYSTEM},
                      {"role": "user", "content": [
                          {"type": "text",
                           "text": f"用户问题：{question}\n\n知识图谱检索结果：\n{context or '（无）'}"},
                          {"type": "image_url",
                           "image_url": {"url": f"data:{mime};base64,{image_b64}"}}]}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    # ---------- 文档辅助 ----------
    def summarize(self, text):
        if not self.available or not text.strip():
            return ""
        return self._chat("你是文档摘要助手，用一句话（50字内）概括医疗文档要点。",
                          text[:4000], temperature=0.3)

    def keywords(self, text):
        if not self.available or not text.strip():
            return []
        raw = self._chat('抽取文本中的关键医疗术语，只输出 JSON 字符串数组，最多8个。',
                         text[:3000])
        arr = _safe_json_array(raw)
        return [x for x in arr if isinstance(x, str)][:8]

    def gen_title(self, question):
        if not self.available:
            return question[:18]
        try:
            t = self._chat("把用户的医疗问题概括成不超过12字的会话标题，只输出标题。",
                           question, temperature=0.3)
            return t.strip().strip("。.\"'")[:18] or question[:18]
        except Exception:
            return question[:18]


def _safe_json_array(raw):
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return []
        return []
