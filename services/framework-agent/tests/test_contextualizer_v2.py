"""Development regressions for Contextualizer v2; no frozen data is loaded here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contextualizer import CONTEXTUALIZER_SYSTEM_PROMPT, needs_contextualization
from evals.contextualizer.validators import evaluate_case

DEV_DATASET = Path(__file__).parents[1] / "evals" / "contextualizer" / "datasets" / "dev.jsonl"


@pytest.mark.parametrize(
    "query",
    [
        "目前还能点吗？",
        "那桂花乌龙怎么样呢？",
        "换成菌菇汤呢？",
        "我说的是冰豆花。",
        "不是红烧肉，我问麻婆豆腐。",
        "不是一份，是四份。",
        "那麻婆豆腐目前还能点吗？",
    ],
    ids=(
        "status-ellipsis",
        "new-entity-ellipsis",
        "replace-entity-ellipsis",
        "explicit-correction",
        "contrasted-entity-correction",
        "quantity-correction",
        "explicit-entity-overrides-history",
    ),
)
def test_v2_gate_routes_structural_followups(query: str) -> None:
    assert needs_contextualization(query, has_history=True) is True


@pytest.mark.parametrize(
    "query",
    [
        "目前还能点吗？",
        "那桂花乌龙怎么样呢？",
        "我说的是冰豆花。",
        "不是一份，是四份。",
    ],
)
def test_v2_gate_never_resolves_without_history(query: str) -> None:
    assert needs_contextualization(query, has_history=False) is False


def test_v2_gate_preserves_standalone_and_confirmation_behavior() -> None:
    assert needs_contextualization("桂花乌龙多少钱？", has_history=False) is False
    assert needs_contextualization("确认。", has_history=True) is False


def test_v2_gate_covers_all_context_dependent_dev_cases_without_routing_no_history() -> None:
    cases = [json.loads(line) for line in DEV_DATASET.read_text(encoding="utf-8").splitlines()]

    assert len(cases) == 30
    with_history = [case for case in cases if case["history"]]
    without_history = [case for case in cases if not case["history"]]
    assert len(with_history) == 24
    assert all(needs_contextualization(case["query"], has_history=True) for case in with_history)
    assert all(
        not needs_contextualization(case["query"], has_history=False) for case in without_history
    )


def test_v2_validator_accepts_allowed_meaning_for_all_dev_cases() -> None:
    cases = [json.loads(line) for line in DEV_DATASET.read_text(encoding="utf-8").splitlines()]
    failures = {
        case["id"]: result["failures"]
        for case in cases
        if not (
            result := evaluate_case(
                case,
                {
                    "id": case["id"],
                    "standaloneQuery": case["expected"]["allowedStandaloneMeaning"][0],
                },
            )
        )["metrics"]["context_resolution_accuracy"]
    }

    assert failures == {}


def test_v2_prompt_defines_precedence_inheritance_replacement_and_ambiguity() -> None:
    prompt = CONTEXTUALIZER_SYSTEM_PROMPT
    correction = prompt.index("current-turn correction")
    explicit_entity = prompt.index("entity explicitly")
    historical_entity = prompt.index("single most recent unambiguous entity")

    assert correction < explicit_entity < historical_entity
    assert "preserve the most recent relevant intent" in prompt
    assert "corrects a quantity, replace the historical quantity" in prompt
    assert "multiple historical entities are equally plausible, do not choose one" in prompt
    assert "do not guess or invent one" in prompt


def _case(
    *,
    case_id: str,
    category: str,
    history: list[dict[str, str]],
    query: str,
    entity: str | None,
    forbidden_entities: list[str],
    intent: str,
    quantity: int | None = None,
    requires_clarification: bool = False,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "category": category,
        "split": "dev",
        "history": history,
        "query": query,
        "expected": {
            "allowedStandaloneMeaning": [],
            "forbiddenEntities": forbidden_entities,
            "intent": intent,
            "mustNotInventFacts": ["18元", "售罄"],
            "mustPreserveFacts": [],
            "quantity": quantity,
            "requiresClarification": requires_clarification,
            "resolvedEntity": entity,
        },
    }


def test_validator_does_not_treat_negated_old_entity_as_active() -> None:
    case = _case(
        case_id="v2_negated_entity",
        category="user_correction",
        history=[
            {"role": "user", "content": "红烧肉怎么卖？"},
            {"role": "assistant", "content": "正在查看红烧肉。"},
        ],
        query="不是红烧肉，我想问麻婆豆腐。",
        entity="麻婆豆腐",
        forbidden_entities=["红烧肉"],
        intent="price",
    )

    result = evaluate_case(
        case,
        {"id": case["id"], "standaloneQuery": "不是红烧肉，我问麻婆豆腐多少钱？"},
    )

    assert result["metrics"]["entity_resolution_accuracy"] is True
    assert "ENTITY_RESOLUTION_ERROR" not in result["failures"]


def test_validator_requires_superseded_quantity_to_be_replaced() -> None:
    case = _case(
        case_id="v2_quantity_replacement",
        category="user_correction",
        history=[
            {"role": "user", "content": "要一杯桂花乌龙。"},
            {"role": "assistant", "content": "已记录一杯桂花乌龙。"},
        ],
        query="不是一杯，是四杯。",
        entity="桂花乌龙",
        forbidden_entities=[],
        intent="add_to_cart",
        quantity=4,
    )

    stale = evaluate_case(
        case,
        {"id": case["id"], "standaloneQuery": "要一杯，再要四杯桂花乌龙。"},
    )
    corrected = evaluate_case(
        case,
        {"id": case["id"], "standaloneQuery": "不要一杯，改为要四杯桂花乌龙。"},
    )

    assert stale["metrics"]["quantity_preservation_accuracy"] is False
    assert "QUANTITY_CHANGED" in stale["failures"]
    assert corrected["metrics"]["quantity_preservation_accuracy"] is True


def test_multi_entity_ambiguity_accepts_safe_unresolved_state_and_rejects_guess() -> None:
    case = _case(
        case_id="v2_multi_entity_ambiguity",
        category="multi_entity_ambiguity",
        history=[
            {"role": "user", "content": "我在比较菌菇汤和冰豆花。"},
            {"role": "assistant", "content": "可以继续了解这两款。"},
        ],
        query="它怎么卖？",
        entity=None,
        forbidden_entities=["菌菇汤", "冰豆花"],
        intent="price",
        requires_clarification=True,
    )

    unresolved = evaluate_case(case, {"id": case["id"], "standaloneQuery": "它多少钱？"})
    guessed = evaluate_case(case, {"id": case["id"], "standaloneQuery": "菌菇汤多少钱？"})

    assert unresolved["metrics"]["context_resolution_accuracy"] is True
    assert guessed["metrics"]["entity_resolution_accuracy"] is False
    assert guessed["metrics"]["clarification_accuracy"] is False


def test_no_history_ambiguity_keeps_entity_unresolved() -> None:
    case = _case(
        case_id="v2_no_history_ambiguity",
        category="no_history_ambiguity",
        history=[],
        query="这个怎么卖？",
        entity=None,
        forbidden_entities=[],
        intent="price",
        requires_clarification=True,
    )

    unresolved = evaluate_case(case, {"id": case["id"], "standaloneQuery": "这个多少钱？"})
    guessed = evaluate_case(case, {"id": case["id"], "standaloneQuery": "冰豆花多少钱？"})

    assert unresolved["metrics"]["context_resolution_accuracy"] is True
    assert guessed["metrics"]["hallucinated_entity_rate"] is True
