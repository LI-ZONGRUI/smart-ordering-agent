"""Deterministic semantic validators for standalone Contextualizer output."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

FAILURES = frozenset(
    {
        "ENTITY_RESOLUTION_ERROR",
        "ENTITY_HALLUCINATION",
        "ENTITY_SWITCH_ERROR",
        "CORRECTION_IGNORED",
        "INTENT_CHANGED",
        "QUANTITY_CHANGED",
        "CLARIFICATION_MISSED",
        "FACT_PRESERVATION_ERROR",
        "UNSUPPORTED_FACT_INJECTION",
        "OUTPUT_CONTRACT_ERROR",
        "MODEL_OUTPUT_INVALID",
    }
)

_OBSERVATION_KEYS = {"id", "standaloneQuery", "modelOutputInvalid"}
_KNOWN_ENTITIES = frozenset(
    {
        "柠檬茶",
        "酸梅汤",
        "拍黄瓜",
        "番茄牛肉面",
        "招牌鸡腿饭",
        "香辣鸡丁",
        "双椒牛肉",
        "红烧肉",
        "杨枝甘露",
        "宫保鸡丁",
        "冰豆花",
        "红糖糍粑",
        "鲜肉小笼包",
        "菌菇汤",
        "桂花乌龙",
        "麻婆豆腐",
    }
)
_PRONOUN_OR_ELLIPSIS = re.compile(
    r"(?:它|这个|那个|这杯|那杯|这份|那份|这道菜|那道菜|多少钱|还有吗|"
    r"能点吗|什么味道|哪些配料|什么配料|来[一二两三四五六七八九十\d]+[杯份个])"
)
_EXPLICIT_CLARIFICATION = re.compile(
    r"(?:请问|麻烦确认|需要确认|需要明确|无法确定|不能确定|不清楚).*(?:指|哪|哪个|哪一)|"
    r"(?:指|说的|想要的).*(?:哪个|哪一个|哪杯|哪道)|(?:柠檬茶|酸梅汤|拍黄瓜|番茄牛肉面|"
    r"招牌鸡腿饭|香辣鸡丁|双椒牛肉|红烧肉|杨枝甘露|宫保鸡丁|冰豆花|红糖糍粑|"
    r"鲜肉小笼包|菌菇汤|桂花乌龙|麻婆豆腐).*还是.*(?:柠檬茶|酸梅汤|拍黄瓜|"
    r"番茄牛肉面|招牌鸡腿饭|香辣鸡丁|双椒牛肉|红烧肉|杨枝甘露|宫保鸡丁|"
    r"冰豆花|红糖糍粑|鲜肉小笼包|菌菇汤|桂花乌龙|麻婆豆腐)"
)
_INTENT_PATTERNS = {
    "price": re.compile(r"(?:多少钱|价格|价钱|售价|卖多少|怎么卖)"),
    "availability": re.compile(r"(?:还有吗|有货|没货|在售|售罄|能点|可以点|供应吗)"),
    "taste": re.compile(r"(?:什么味道|口味|味道|好喝|好吃|辣吗|甜吗|酸吗)"),
    "ingredients": re.compile(r"(?:配料|食材|原料|什么做的|含有)"),
    "add_to_cart": re.compile(
        r"(?:加入?购物车|加到购物车|(?:来|要|点|加|上).{0,12}?"
        r"(?:[一二两三四五六七八九十\d]+)\s*(?:杯|份|个))"
    ),
}
_QUANTITY = re.compile(r"([一二两三四五六七八九十\d]+)\s*(?:杯|份|个)")
_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_NEW_FACT_PATTERNS = (
    re.compile(r"\d+(?:\.\d+)?\s*元"),
    re.compile(r"(?:大杯|中杯|小杯|少冰|去冰|加冰|少糖|无糖|加糖)"),
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[\s，。！？、；：,.!?;:'\"“”‘’（）()]+", "", normalized)


def _entities(text: str) -> set[str]:
    return {entity for entity in _KNOWN_ENTITIES if entity in text}


def _intent(text: str) -> str | None:
    # Action must win over the generic word “点”; the action pattern requires a quantity or cart.
    if _INTENT_PATTERNS["add_to_cart"].search(text):
        return "add_to_cart"
    for intent in ("price", "availability", "taste", "ingredients"):
        if _INTENT_PATTERNS[intent].search(text):
            return intent
    return None


def _quantities(text: str) -> set[int]:
    values: set[int] = set()
    for match in _QUANTITY.finditer(text):
        token = match.group(1)
        if token.isdigit():
            values.add(int(token))
        elif token in _CHINESE_NUMBERS:
            values.add(_CHINESE_NUMBERS[token])
    return values


def _source_text(case: dict[str, Any]) -> str:
    history = "\n".join(message["content"] for message in case["history"])
    return f"{history}\n{case['query']}"


def _actual_clarification(case: dict[str, Any], output: str) -> bool:
    if _EXPLICIT_CLARIFICATION.search(output):
        return True
    if not case["expected"]["requiresClarification"]:
        return False
    # The production contract has no clarification boolean. Safely retaining an unresolved
    # reference/ellipsis is accepted, provided the model did not select an entity.
    return not _entities(output) and _PRONOUN_OR_ELLIPSIS.search(output) is not None


def _unsupported_fact_injection(case: dict[str, Any], output: str) -> bool:
    expected = case["expected"]
    if any(fact in output for fact in expected["mustNotInventFacts"]):
        return True
    source = _source_text(case)
    for pattern in _NEW_FACT_PATTERNS:
        for match in pattern.finditer(output):
            if normalize_text(match.group(0)) not in normalize_text(source):
                return True
    return False


def _empty_metrics() -> dict[str, bool | None]:
    return {
        "context_resolution_accuracy": False,
        "entity_resolution_accuracy": False,
        "intent_preservation_accuracy": False,
        "quantity_preservation_accuracy": None,
        "clarification_accuracy": False,
        "hallucinated_entity_rate": None,
        "unsupported_fact_injection_rate": None,
        "normalized_string_match": None,
    }


def evaluate_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """Score semantics without requiring character-for-character output equality."""

    failures: list[str] = []
    expected = case["expected"]
    if (
        not isinstance(observation, dict)
        or any(key not in _OBSERVATION_KEYS for key in observation)
        or observation.get("id") != case["id"]
        or (
            "modelOutputInvalid" in observation
            and type(observation["modelOutputInvalid"]) is not bool
        )
    ):
        failures.append("OUTPUT_CONTRACT_ERROR")
        return _result(case, _empty_metrics(), failures)

    if observation.get("modelOutputInvalid") is True:
        failures.append("MODEL_OUTPUT_INVALID")
        metrics = _empty_metrics()
        if expected["quantity"] is not None:
            metrics["quantity_preservation_accuracy"] = False
        return _result(case, metrics, failures)

    output = observation.get("standaloneQuery")
    if not isinstance(output, str) or not output.strip() or len(output.strip()) > 200:
        failures.append("OUTPUT_CONTRACT_ERROR")
        metrics = _empty_metrics()
        if expected["quantity"] is not None:
            metrics["quantity_preservation_accuracy"] = False
        return _result(case, metrics, failures)
    output = output.strip()

    actual_entities = _entities(output)
    source_entities = _entities(_source_text(case))
    hallucinated = bool(actual_entities - source_entities)
    clarification = _actual_clarification(case, output)
    expected_entity = expected["resolvedEntity"]
    if expected_entity is None:
        entity_ok = clarification
        if not clarification and actual_entities & set(expected["forbiddenEntities"]):
            entity_ok = False
    else:
        entity_ok = expected_entity in actual_entities and not (
            (actual_entities - {expected_entity}) & set(expected["forbiddenEntities"])
        )

    intent_ok = _intent(output) == expected["intent"]
    expected_quantity = expected["quantity"]
    quantity_ok = (
        expected_quantity in _quantities(output) if expected_quantity is not None else None
    )
    clarification_ok = clarification is expected["requiresClarification"]
    preserved_facts = all(
        normalize_text(fact) in normalize_text(output) for fact in expected["mustPreserveFacts"]
    )
    unsupported = _unsupported_fact_injection(case, output)
    normalized_match = normalize_text(output) in {
        normalize_text(value) for value in expected["allowedStandaloneMeaning"]
    }
    context_ok = all(
        value is True
        for value in (
            entity_ok,
            intent_ok,
            clarification_ok,
            preserved_facts,
            not hallucinated,
            not unsupported,
        )
    ) and (quantity_ok is not False)

    if not entity_ok:
        failures.append("ENTITY_RESOLUTION_ERROR")
        if case["category"] == "entity_switch":
            failures.append("ENTITY_SWITCH_ERROR")
    if hallucinated:
        failures.append("ENTITY_HALLUCINATION")
    if not intent_ok:
        failures.append("INTENT_CHANGED")
    if quantity_ok is False:
        failures.append("QUANTITY_CHANGED")
    if not clarification_ok:
        failures.append("CLARIFICATION_MISSED")
    if not preserved_facts:
        failures.append("FACT_PRESERVATION_ERROR")
    if unsupported:
        failures.append("UNSUPPORTED_FACT_INJECTION")
    if case["category"] == "user_correction" and not context_ok:
        failures.append("CORRECTION_IGNORED")

    metrics: dict[str, bool | None] = {
        "context_resolution_accuracy": context_ok,
        "entity_resolution_accuracy": entity_ok,
        "intent_preservation_accuracy": intent_ok,
        "quantity_preservation_accuracy": quantity_ok,
        "clarification_accuracy": clarification_ok,
        "hallucinated_entity_rate": hallucinated,
        "unsupported_fact_injection_rate": unsupported,
        "normalized_string_match": normalized_match,
    }
    return _result(case, metrics, failures)


def _result(
    case: dict[str, Any], metrics: dict[str, bool | None], failures: list[str]
) -> dict[str, Any]:
    unique_failures = list(dict.fromkeys(failures))
    return {
        "id": case["id"],
        "category": case["category"],
        "split": case["split"],
        "metrics": metrics,
        "failures": unique_failures,
        "primaryFailure": unique_failures[0] if unique_failures else None,
        "secondaryFailures": unique_failures[1:],
    }
