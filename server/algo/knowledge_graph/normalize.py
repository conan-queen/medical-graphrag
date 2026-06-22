"""实体名称归一化：清洗 + 同义词归并，提升图谱质量与检索准确度。

策略：
  1) 去除首尾空白与常见标点；
  2) 命中内置同义词表 → 归并到规范名；
  3) 其余保持原样（保守，避免误并）。
可按需扩充 SYNONYMS。
"""
import re

# 规范名 -> 别名列表
_CANON = {
    "原发性高血压": ["高血压", "高血压病", "原发高血压", "essential hypertension"],
    "2型糖尿病": ["二型糖尿病", "ii型糖尿病", "2型糖尿病(t2dm)", "糖尿病2型", "type 2 diabetes"],
    "急性上呼吸道感染": ["上呼吸道感染", "上感", "感冒", "普通感冒"],
    "流行性感冒": ["流感", "流行感冒", "influenza"],
    "慢性胃炎": ["胃炎"],
    "幽门螺杆菌感染": ["幽门螺杆菌", "hp感染", "hp"],
    "空腹血糖": ["fpg", "空腹血糖值"],
    "糖化血红蛋白": ["hba1c", "糖化血红蛋白(hba1c)"],
}

# 反向索引：别名(小写) -> 规范名
_ALIAS = {}
for canon, aliases in _CANON.items():
    for a in aliases:
        _ALIAS[a.lower()] = canon
    _ALIAS[canon.lower()] = canon


def canonical(name: str) -> str:
    if not name:
        return name
    s = name.strip().strip("。.，,、；;：:（）()【】[]\"' ")
    s = re.sub(r"\s+", "", s)
    return _ALIAS.get(s.lower(), s)


def normalize_triples(triples):
    """归一化三元组的头尾实体，并按 (头,关系,尾) 去重。"""
    seen, out = set(), []
    for t in triples:
        h = canonical(t.get("head", ""))
        ta = canonical(t.get("tail", ""))
        rel = (t.get("relation") or "").strip()
        if not h or not ta or not rel or h == ta:
            continue
        key = (h, rel, ta)
        if key in seen:
            continue
        seen.add(key)
        out.append({"head": h, "head_type": t.get("head_type", "实体"),
                    "relation": rel, "tail": ta, "tail_type": t.get("tail_type", "实体")})
    return out
