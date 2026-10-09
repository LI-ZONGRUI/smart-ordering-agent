"""Bounded Chinese assertion checks for Validator v2, not a semantic entailment model.

Negation is scoped to a predicate inside its clause. Unrecognized/conditional wording needs
human review; uncertainty never turns an eligible metric into N/A or an automatic success.
Only fixed reason codes and booleans leave this module, never answer spans.
"""

from __future__ import annotations

import re
from typing import Any

FAILURE_REASONS = frozenset(
    {
        "STATUS_MISMATCH",
        "PRICE_MISMATCH",
        "EMPTY_RESULT_ASSERTION",
        "REQUIRED_KEYWORD_MISSING",
        "FORBIDDEN_PHRASE_MATCH",
        "ENTITY_REFERENCE_MISSING",
        "UNSUPPORTED_ABSOLUTE_CLAIM",
        "INDETERMINATE_SEMANTIC_CHECK",
        "RESULT_ENTITY_MISMATCH",
    }
)
_SPLIT = re.compile(r"[，,。；;\n！？!?]|但是|不过|然而|但(?!是)|而是|而且|并且")
_AVAILABILITY = re.compile(r"在售|(?:可以|能够|能|可)(?:正常)?(?:下单|购买|点单)|有库存")
_SOLD_OUT = re.compile(r"(?:已|已经)?售罄|(?:已经|已)?卖完(?:了)?|缺货|无库存")
_NEGATION = re.compile(
    r"(?:并不是|不是|不属于|并非|并不|不再|不能|没有|暂未|尚未|未|没|不|无)"
    r"(?:是|处于|属于|显示|发现|查到|找到|搜到|检索到|看到|确认|确定|有|"
    r"目前|当前|现在|仍然|仍|正常|已经|已|符合条件的|店里|本店|餐厅|菜单上|记录中|结果中|也|\s)*$"
)
_META = re.compile(
    r"(?:不代表|不等于|不是说|并非说|不能说明|不能据此(?:认定|确定|断定)?|不能说|不能断定|不能推断|无法断定)[^，。；]*$"
)
_UNCERTAIN = re.compile(
    r"如果|假如|是否|能否|可能|也许|似乎|大概|据说|听说|不确定|无法确认|不能确定"
)
_DOUBLE_NEGATIVE = re.compile(r"不是不|并非不|不能不|没有不|不无")
_REFERENCE = re.compile(r"这款|这杯|这个|该菜|该饮品|它")
_SEARCH_NEGATIVE = re.compile(r"(?:没有|暂未|尚未|未|没)(?:查到|找到|发现|搜到|检索到)")


def clauses(answer: str) -> list[str]:
    return [part.strip() for part in _SPLIT.split(answer) if part.strip()]


def polarity(clause: str, start: int, entity: str = "") -> str:
    """Recognize local positive/negative assertions, explicit non-assertions and uncertainty."""

    prefix = clause[:start]
    if _META.search(prefix):
        return "not_asserted"
    if _UNCERTAIN.search(clause) or _DOUBLE_NEGATIVE.search(prefix):
        return "indeterminate"
    # The subject may sit between a search negation and the predicate: 未发现有可乐在售.
    if entity:
        prefix = prefix.replace(entity, "")
    return "negative" if _NEGATION.search(prefix) else "positive"


def forbidden_phrase_check(answer: str, terms: list[str]) -> tuple[bool, bool]:
    matched = uncertain = False
    for clause in clauses(answer):
        for term in terms:
            for match in re.finditer(re.escape(term), clause):
                state = polarity(clause, match.start())
                matched |= state == "positive"
                uncertain |= state == "indeterminate"
    return matched, uncertain


def required_group_hits(
    answer: str, groups: list[list[str]], analysis: dict[str, Any]
) -> list[bool]:
    """Permit established conservative empty-search synonyms, not arbitrary semantic guesses."""

    return [
        any(term in answer for term in group)
        or (
            all(_SEARCH_NEGATIVE.fullmatch(term) for term in group)
            and analysis.get("emptySearchCheck") == "pass"
        )
        for group in groups
    ]


def analyze_answer(trace: list[dict[str, Any]], answer: str) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    empty_queries: list[str] = []
    searches: dict[int, list[str]] = {}
    ambiguous_empty_result = False
    for event in trace:
        if (
            event.get("eventType") == "assistant_tool_call"
            and event.get("toolName") == "search_menu"
        ):
            query = event.get("arguments", {}).get("query")
            if isinstance(query, str):
                searches.setdefault(event["step"], []).append(query)
        if event.get("eventType") != "tool_result":
            continue
        summary = event.get("summary", {})
        if event.get("resultClass") == "empty" and event.get("toolName") == "search_menu":
            queries = searches.get(event["step"], [])
            if len(queries) == 1:
                empty_queries.append(queries[0])
            else:
                # No correlation IDs are exported. Never guess which parallel query was empty.
                ambiguous_empty_result = True
        values = list(summary.get("items", []))
        if isinstance(summary.get("item"), dict):
            values.append(summary["item"])
        for item in values:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                items[item["name"]] = item

    reasons: set[str] = set()
    key_fact = False
    status_seen = price_seen = empty_seen = False
    status_unknown = price_unknown = empty_unknown = False
    entity_mentioned = any(name in answer for name in items)
    active: str | None = None
    for clause in clauses(answer):
        named = [name for name in items if name in clause]
        if len(named) == 1:
            active = named[0]
        elif len(named) > 1:
            active = None
        elif _REFERENCE.search(clause) and len(items) == 1:
            active = next(iter(items))
        elif re.search(r"其他|别的|另一(?:款|杯|个)|另外一种", clause):
            active = None
        facts = [*_AVAILABILITY.finditer(clause), *_SOLD_OUT.finditer(clause)]
        if facts and active is None and items:
            status_unknown = True
        if active is not None:
            item = items[active]
            if re.search(r"\d+(?:\.\d+)?\s*(?:块|RMB)|[¥￥]\s*\d", clause, re.IGNORECASE):
                price_unknown = True
            for pattern, positive_status in ((_AVAILABILITY, "on_sale"), (_SOLD_OUT, "sold_out")):
                for match in pattern.finditer(clause):
                    state = polarity(clause, match.start(), active)
                    status_seen = True
                    if state == "indeterminate":
                        status_unknown = True
                    elif state != "not_asserted":
                        asserted = (
                            positive_status
                            if state == "positive"
                            else ("sold_out" if positive_status == "on_sale" else "on_sale")
                        )
                        if asserted != item.get("status"):
                            reasons.add("STATUS_MISMATCH")
                        else:
                            key_fact = True
            for match in re.finditer(r"(?:单价|价格|售价)?\s*(\d+(?:\.\d+)?)\s*元", clause):
                before = clause[: match.start()]
                if not any(
                    word in match.group() for word in ("单价", "价格", "售价")
                ) and re.search(r"(?:合计|总共|总价|总计|两杯|两份)[^元]*$", before):
                    continue
                price_seen = True
                state = polarity(clause, match.start(), active)
                equal = float(match.group(1)) == item.get("price")
                if state == "indeterminate":
                    price_unknown = True
                elif state == "positive":
                    if equal:
                        key_fact = True
                    else:
                        reasons.add("PRICE_MISMATCH")
                elif state == "negative" and equal:
                    reasons.add("PRICE_MISMATCH")
            # Existence/recommendation references are distinct from availability/price claims.
            for match in re.finditer(
                rf"(?:有|查到|找到|查询到|包括|返回)\s*{re.escape(active)}", clause
            ):
                state = polarity(clause, match.start(), active)
                if state == "positive":
                    key_fact = True
                elif state == "negative":
                    reasons.add("RESULT_ENTITY_MISMATCH")
                elif state == "indeterminate":
                    status_unknown = True
            if active in clause and re.search(r"可以考虑|可以看看|有的", clause):
                key_fact |= item.get("status") == "on_sale"
            for ingredient in item.get("ingredients", []):
                for match in re.finditer(re.escape(ingredient), clause):
                    if polarity(clause, match.start(), active) == "positive":
                        key_fact = True

    for query in dict.fromkeys(empty_queries):
        q = re.escape(query)
        cautious = False
        for clause in clauses(answer):
            if query not in clause:
                continue
            if _SEARCH_NEGATIVE.search(clause) and not _UNCERTAIN.search(clause):
                cautious = empty_seen = True
                key_fact = True
            patterns = [
                rf"(?:有|找到(?:了)?|查到(?:了)?|发现(?:了)?|搜到(?:了)?|检索到(?:了)?)\s*(?:符合条件的)?{q}",
                rf"{q}\s*(?:目前|当前|现在)?\s*(?:在售|可以下单|可以购买)",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, clause):
                    state = polarity(clause, match.start(), query)
                    if state == "positive":
                        reasons.add("EMPTY_RESULT_ASSERTION")
                    elif state == "indeterminate":
                        empty_unknown = True
            # A narrow search cannot prove global absence or availability.
            absolute = re.finditer(
                rf"(?:店里|本店|餐厅|菜单上).{{0,4}}(?:绝对|肯定)?(?:没有|无|不卖){q}"
                rf"|(?:绝对|肯定)(?:没有|不存在){q}|{q}(?:绝对)?不存在"
                rf"|没有{q}|{q}(?:目前|现在)?不在售",
                clause,
            )
            for match in absolute:
                state = polarity(clause, match.start(), query)
                if state == "positive":
                    reasons.add("UNSUPPORTED_ABSOLUTE_CLAIM")
                elif state == "indeterminate":
                    empty_unknown = True
        if not cautious and not reasons:
            empty_unknown = True

    empty_unknown |= ambiguous_empty_result
    unknown = status_unknown or price_unknown or empty_unknown
    if (items or empty_queries) and not key_fact and not reasons:
        unknown = True
    if unknown:
        reasons.add("INDETERMINATE_SEMANTIC_CHECK")
    definite = reasons - {"INDETERMINATE_SEMANTIC_CHECK"}
    return {
        "consistency": "fail" if definite else "indeterminate" if unknown else "pass",
        "entityMentioned": entity_mentioned,
        "keyFactsReferenced": key_fact,
        "reasons": sorted(reasons),
        "statusCheck": "fail"
        if "STATUS_MISMATCH" in reasons
        else "indeterminate"
        if status_unknown
        else "pass"
        if status_seen
        else "not_observed",
        "priceCheck": "fail"
        if "PRICE_MISMATCH" in reasons
        else "indeterminate"
        if price_unknown
        else "pass"
        if price_seen
        else "not_observed",
        "emptySearchCheck": "fail"
        if {"EMPTY_RESULT_ASSERTION", "UNSUPPORTED_ABSOLUTE_CLAIM"} & reasons
        else "indeterminate"
        if empty_unknown
        else "pass"
        if empty_seen
        else "not_observed",
    }
