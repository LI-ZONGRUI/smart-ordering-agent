"""Bounded, deterministic Dev answer checks. No model, network or persisted answer.

PASS means recognized contracts passed, not complete semantic entailment. Unknown grammar
stays REVIEW; machine-detected FAIL is not an independently human-verified model error.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from evals.tool_replanning.answer_checks import required_group_hits as required_group_hits

BRANCH_CODES = frozenset(
    {
        "PRICE_FORMAT_RECOGNIZED",
        "PRICE_FORMAT_UNRESOLVED",
        "PRICE_VALUE_MISMATCH",
        "PRICE_TOTAL_EXCLUDED",
        "NEGATION_SCOPE_RESOLVED",
        "NEGATION_SCOPE_UNRESOLVED",
        "CONDITIONAL_SCOPE_UNRESOLVED",
        "UNCERTAIN_ASSERTION",
        "DOUBLE_NEGATION_UNRESOLVED",
        "TEMPORAL_SCOPE_UNRESOLVED",
        "REPORTED_ASSERTION_UNRESOLVED",
        "ENTITY_ATTRIBUTION_UNRESOLVED",
        "STATUS_SYNONYM_RECOGNIZED",
        "STATUS_MISMATCH",
        "KEY_FACT_UNRECOGNIZED",
        "EMPTY_RESULT_MAPPING_UNRESOLVED",
        "EMPTY_SEARCH_RECOGNIZED",
        "EMPTY_RESULT_ASSERTION",
        "UNSUPPORTED_ABSOLUTE_CLAIM",
        "TOOL_FACT_CONFLICT",
        "REQUIRED_KEYWORD_MISSING",
        "ENTITY_REFERENCE_MISSING",
        "FORBIDDEN_PHRASE_MATCH",
        "ANSWER_MISSING",
        "TRACE_CONTRACT_INVALID",
        "REVIEW_REQUIRED",
    }
)
_SPLIT = re.compile(r"([，,。；;\n！？!?]|但是|不过|然而|但(?!是)|而是|而且|并且)")
_CONDITION = re.compile(r"如果|假如|倘若|若是|只要")
_UNCERTAIN = re.compile(r"是否|能否|可能|也许|似乎|大概|不确定|无法确认|不能确定")
_TEMPORAL = re.compile(r"以前|曾经|过去|明天|将来|到时|恢复后")
_REPORTED = re.compile(r"用户说|你说|你问|有人说|据说|听说|引用")
_DOUBLE = re.compile(r"不是不|并非不|不能不|没有不|不无")
_META = re.compile(r"不代表|不等于|不是说|并非说|不能说明|不能据此|不能说|不能断定|无法断定")
_NEGATIVE = re.compile(
    r"(?:并不是|不是|不属于|并非|并不|不再|不能|没有|暂未|尚未|未|没|不|无)"
    r"(?:是|处于|处在|属于|显示|发现|查到|找到|搜到|检索到|看到|确认|确定|有|"
    r"目前|当前|现在|仍然|仍|正常|已经|已|符合条件的|店里|本店|餐厅|菜单上|记录中|结果中|也|\s)*$"
)
_QUOTES = str.maketrans("", "", "‘’“”\"'（）()")
_STATUS = re.compile(
    r"(?P<unavailable>买不到|无法(?:正常)?(?:购买|买|下单|点单)|不能(?:正常)?(?:购买|买|下单|点单)|不可购买)"
    r"|(?P<sold>(?:已|已经)?售罄|(?:已经|已)?卖完(?:了)?|缺货|无库存)"
    r"|(?P<available>在售|(?:可以|能够|还能|能|可)(?:正常)?(?:下单|购买|买|点单)|有库存)"
)
_NUMBER = r"\d+(?:\.\d+)?"
_PRICE = re.compile(
    rf"(?<![A-Za-z0-9_.\-])(?:(?:RMB|人民币)\s*(?P<prefix>{_NUMBER})|[¥￥]\s*(?P<symbol>{_NUMBER})"
    rf"|(?P<suffix>{_NUMBER})\s*(?:元|块)(?:钱)?)(?![\d.])",
    re.IGNORECASE,
)
_SEARCH_NEGATIVE = re.compile(r"(?:没有|暂未|尚未|未|没)(?:查到|找到|发现|搜到|检索到)")
_REFERENCE = re.compile(r"这款|这杯|这个|该菜|该饮品|它")


def segments(answer: str) -> list[tuple[str, bool]]:
    """Keep a leading conditional across comma-separated consequent, not across sentences."""
    output = []
    carry = False
    for part in _SPLIT.split(answer):
        if _SPLIT.fullmatch(part):
            if part in {"?", "？"} and output:
                text, was_conditional = output[-1]
                output[-1] = (text + part, was_conditional)
            if part in "。；;\n！？!?" or part in {"但是", "不过", "然而", "而是"}:
                carry = False
            continue
        if not part.strip():
            continue
        output.append((part.strip(), carry))
        # A condition added after a completed assertion must not contaminate that assertion.
        condition = _CONDITION.search(part)
        facts = [match for pattern in (_STATUS, _PRICE) if (match := pattern.search(part))]
        if condition and (not facts or condition.start() < min(m.start() for m in facts)):
            carry = True
    return output


def polarity(
    clause: str, start: int, entity: str = "", *, conditional: bool = False
) -> tuple[str, set[str]]:
    prefix = clause[:start].translate(_QUOTES)
    branches: set[str] = set()
    if _META.search(prefix):
        return "not_asserted", branches
    if conditional or _CONDITION.search(prefix):
        return "review", {"CONDITIONAL_SCOPE_UNRESOLVED"}
    if _DOUBLE.search(prefix):
        return "review", {"DOUBLE_NEGATION_UNRESOLVED"}
    if clause.endswith(("?", "？")) or _UNCERTAIN.search(prefix):
        return "review", {"UNCERTAIN_ASSERTION"}
    if _TEMPORAL.search(prefix):
        return "review", {"TEMPORAL_SCOPE_UNRESOLVED"}
    if _REPORTED.search(prefix):
        return "review", {"REPORTED_ASSERTION_UNRESOLVED"}
    if entity:
        prefix = prefix.replace(entity, "")
    if _NEGATIVE.search(prefix):
        return "negative", {"NEGATION_SCOPE_RESOLVED"}
    # Recognize only bounded grammar. Do not silently turn unparsed negation into affirmation.
    recent = prefix[-10:]
    recent = re.sub(r"不(?:辣|想|需要|喜欢)[^在]*", "", recent)
    if re.search(r"不|没|未|无", recent):
        return "review", {"NEGATION_SCOPE_UNRESOLVED"}
    return "positive", branches


def forbidden_phrase_check(answer: str, terms: list[str]) -> tuple[bool, bool, set[str]]:
    matched = review = False
    branches: set[str] = set()
    for clause, conditional in segments(answer):
        for term in terms:
            for match in re.finditer(re.escape(term), clause):
                state, codes = polarity(clause, match.start(), conditional=conditional)
                branches.update(codes)
                matched |= state == "positive"
                review |= state == "review"
    if matched:
        branches.add("FORBIDDEN_PHRASE_MATCH")
    return matched, review, branches


def analyze_answer(trace: list[dict[str, Any]], answer: str) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    searches: dict[int, list[str]] = {}
    empty_queries = []
    reasons: set[str] = set()
    branches: set[str] = set()
    for event in trace:
        if (
            event.get("eventType") == "assistant_tool_call"
            and event.get("toolName") == "search_menu"
        ):
            searches.setdefault(event["step"], []).append(
                event.get("arguments", {}).get("query", "")
            )
        if event.get("eventType") != "tool_result":
            continue
        summary = event.get("summary", {})
        if event.get("toolName") == "search_menu" and event.get("resultClass") == "empty":
            queries = searches.get(event["step"], [])
            if len(queries) == 1:
                empty_queries.append(queries[0])
            else:
                branches.add("EMPTY_RESULT_MAPPING_UNRESOLVED")
        values = list(summary.get("items", []))
        if isinstance(summary.get("item"), dict):
            values.append(summary["item"])
        for item in values:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                previous = items.get(item["name"])
                if previous and any(previous.get(k) != item.get(k) for k in ("price", "status")):
                    branches.add("TOOL_FACT_CONFLICT")
                items[item["name"]] = item

    key_fact = False
    seen = {"status": False, "price": False, "empty": False}
    unknown = {"status": False, "price": False, "empty": False}
    active: str | None = None
    for clause, conditional in segments(answer):
        named = [name for name in items if name in clause]
        if len(named) == 1:
            active = named[0]
        elif len(named) > 1:
            active = None
        elif _REFERENCE.search(clause) and len(items) == 1:
            active = next(iter(items))
        elif re.search(r"其他|别的|另一(?:款|杯|个)|另外一种", clause):
            active = None

        def entity_for(
            start: int, clause: str = clause, named: list[str] = named, active: str | None = active
        ) -> str | None:
            # Multiple entities in one clause: accept explicitly separated predicates only.
            before = [(clause.rfind(name, 0, start), name) for name in named]
            preceding = sorted((pos, name) for pos, name in before if pos >= 0)
            if len(named) > 1:
                if not preceding:
                    return None
                if len(preceding) > 1:
                    left, right = preceding[-2], preceding[-1]
                    bridge = clause[left[0] + len(left[1]) : right[0]]
                    if re.fullmatch(r"\s*(?:和|与|、|及)\s*", bridge):
                        return None
                return preceding[-1][1]
            return active

        for match in _STATUS.finditer(clause):
            seen["status"] = True
            branches.add("STATUS_SYNONYM_RECOGNIZED")
            entity = entity_for(match.start())
            if entity is None:
                if items:
                    unknown["status"] = True
                    branches.add("ENTITY_ATTRIBUTION_UNRESOLVED")
                continue
            state, codes = polarity(clause, match.start(), entity, conditional=conditional)
            if re.match(r"(?:过|吗|么|吧)", clause[match.end() :]):
                state = "review"
                codes.add(
                    "TEMPORAL_SCOPE_UNRESOLVED"
                    if clause[match.end() :].startswith("过")
                    else "UNCERTAIN_ASSERTION"
                )
            branches.update(codes)
            negative_phrase = match.lastgroup == "unavailable"
            if negative_phrase and state == "negative":
                state = "review"
                branches.add("DOUBLE_NEGATION_UNRESOLVED")
            if state == "review":
                unknown["status"] = True
            elif state != "not_asserted":
                base = "on_sale" if match.lastgroup == "available" else "sold_out"
                asserted = (
                    base
                    if state == "positive"
                    else ("sold_out" if base == "on_sale" else "on_sale")
                )
                if asserted != items[entity].get("status"):
                    reasons.add("STATUS_MISMATCH")
                    branches.add("STATUS_MISMATCH")
                else:
                    key_fact = True

        price_matches = list(_PRICE.finditer(clause))
        if items and re.search(r"[¥￥]|RMB\s|人民币", clause, re.IGNORECASE):
            covered = _PRICE.sub("", clause)
            if re.search(r"[¥￥]|RMB\s|人民币", covered, re.IGNORECASE):
                unknown["price"] = True
                branches.add("PRICE_FORMAT_UNRESOLVED")
        for match in price_matches:
            prefix = clause[: match.start()]
            if re.search(
                r"(?:合计|总共|总价|总计|两杯|两份)[^元块¥￥]*$", prefix
            ) and not re.search(r"单价|价格|售价", prefix):
                branches.add("PRICE_TOTAL_EXCLUDED")
                continue
            seen["price"] = True
            branches.add("PRICE_FORMAT_RECOGNIZED")
            entity = entity_for(match.start())
            if entity is None:
                if items:
                    unknown["price"] = True
                    branches.add("ENTITY_ATTRIBUTION_UNRESOLVED")
                continue
            state, codes = polarity(clause, match.start(), entity, conditional=conditional)
            branches.update(codes)
            value = next(value for value in match.groupdict().values() if value is not None)
            equal = Decimal(value) == Decimal(str(items[entity].get("price")))
            if state == "review":
                unknown["price"] = True
            elif state == "positive" and not equal or state == "negative" and equal:
                reasons.add("PRICE_MISMATCH")
                branches.add("PRICE_VALUE_MISMATCH")
            elif state == "positive" and equal:
                key_fact = True

        if active:
            for match in re.finditer(
                rf"(?:有|查到|找到|查询到|包括|返回)\s*{re.escape(active)}", clause
            ):
                state, codes = polarity(clause, match.start(), active, conditional=conditional)
                branches.update(codes)
                if state == "positive":
                    key_fact = True
                elif state == "negative":
                    reasons.add("RESULT_ENTITY_MISMATCH")
                elif state == "review":
                    unknown["status"] = True
            if active in clause and re.search(r"可以考虑|可以看看|有的", clause):
                state, codes = polarity(
                    clause, clause.find(active), active, conditional=conditional
                )
                branches.update(codes)
                key_fact |= state == "positive" and items[active].get("status") == "on_sale"
            for ingredient in items[active].get("ingredients", []):
                for match in re.finditer(re.escape(ingredient), clause):
                    state, codes = polarity(clause, match.start(), active, conditional=conditional)
                    branches.update(codes)
                    key_fact |= state == "positive"

    for query in dict.fromkeys(empty_queries):
        cautious = False
        for clause, conditional in segments(answer):
            if query not in clause:
                continue
            q = re.escape(query)
            match = _SEARCH_NEGATIVE.search(clause)
            if match:
                state, codes = polarity(clause, match.start(), query, conditional=conditional)
                branches.update(codes)
                if state == "positive":
                    cautious = seen["empty"] = key_fact = True
                    branches.add("EMPTY_SEARCH_RECOGNIZED")
                elif state == "review":
                    unknown["empty"] = True
            for pattern in (
                rf"(?:有|找到(?:了)?|查到(?:了)?|发现(?:了)?)\s*(?:符合条件的)?{q}",
                rf"{q}\s*(?:目前|当前|现在)?\s*(?:在售|可以下单|可以购买)",
            ):
                for match in re.finditer(pattern, clause):
                    state, codes = polarity(clause, match.start(), query, conditional=conditional)
                    branches.update(codes)
                    if state == "positive":
                        reasons.add("EMPTY_RESULT_ASSERTION")
                        branches.add("EMPTY_RESULT_ASSERTION")
                    elif state == "review":
                        unknown["empty"] = True
            for match in re.finditer(
                rf"(?:店里|本店|餐厅|菜单上).{{0,4}}(?:绝对|肯定)?(?:没有|无|不卖){q}|(?:绝对|肯定)(?:没有|不存在){q}|{q}(?:绝对)?不存在|没有{q}|{q}(?:目前|现在)?不在售",
                clause,
            ):
                state, codes = polarity(clause, match.start(), query, conditional=conditional)
                branches.update(codes)
                if state == "positive":
                    reasons.add("UNSUPPORTED_ABSOLUTE_CLAIM")
                    branches.add("UNSUPPORTED_ABSOLUTE_CLAIM")
                elif state == "review":
                    unknown["empty"] = True
        if not cautious and not reasons:
            unknown["empty"] = True
            branches.add("KEY_FACT_UNRECOGNIZED")

    review = any(unknown.values()) or bool(
        branches & {"EMPTY_RESULT_MAPPING_UNRESOLVED", "TOOL_FACT_CONFLICT"}
    )
    if (items or empty_queries) and not key_fact and not reasons:
        review = True
        branches.add("KEY_FACT_UNRECOGNIZED")
    if review:
        reasons.add("INDETERMINATE_SEMANTIC_CHECK")
        branches.add("REVIEW_REQUIRED")
    definite = reasons - {"INDETERMINATE_SEMANTIC_CHECK"}
    verdict = "FAIL" if definite else "REVIEW" if review else "PASS"
    return {
        "verdict": verdict,
        "consistency": {"PASS": "pass", "FAIL": "fail", "REVIEW": "indeterminate"}[verdict],
        "entityMentioned": any(name in answer for name in items),
        "keyFactsReferenced": key_fact,
        "reasons": sorted(reasons),
        "branchCodes": sorted(branches),
        "statusCheck": "fail"
        if "STATUS_MISMATCH" in reasons
        else "indeterminate"
        if unknown["status"]
        else "pass"
        if seen["status"]
        else "not_observed",
        "priceCheck": "fail"
        if "PRICE_MISMATCH" in reasons
        else "indeterminate"
        if unknown["price"]
        else "pass"
        if seen["price"]
        else "not_observed",
        "emptySearchCheck": "fail"
        if {"EMPTY_RESULT_ASSERTION", "UNSUPPORTED_ABSOLUTE_CLAIM"} & reasons
        else "indeterminate"
        if unknown["empty"]
        else "pass"
        if seen["empty"]
        else "not_observed",
    }
