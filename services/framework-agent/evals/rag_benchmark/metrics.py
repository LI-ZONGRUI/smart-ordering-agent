"""Applicable denominators are retained, including REVIEW and failed requests."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evals.rag_benchmark.validators import ERROR, METRICS


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {}
    for name in METRICS:
        rows = [r for r in results if r["metrics"][name] is not None]
        counts = Counter(r["metrics"][name] for r in rows)
        total = len(rows)
        observed = [r["values"][name] for r in rows if r["values"][name] is not None]
        # Error rates are lower bounds when REVIEW remains; never silently remove reviews.
        numeric = sum(float(v) for v in observed) / total if total and observed else None
        metrics[name] = {
            "applicable": total,
            "pass": counts["PASS"],
            "machineDetectedFail": counts["FAIL"],
            "review": counts["REVIEW"],
            "conservativeAutomaticPassRate": counts["PASS"] / total if total else None,
            "determinateCheckCoverage": (total - counts["REVIEW"]) / total if total else None,
            "value": numeric,
            "valueMeaning": "observed-error-lower-bound" if name in ERROR else "conservative-score",
        }
    return {
        "metrics": metrics,
        "casesRequiringReview": sum(bool(r["reviewReasons"]) for r in results),
        "failureDistribution": dict(Counter(c for r in results for c in r["failureCodes"])),
        "reviewDistribution": dict(Counter(c for r in results for c in r["reviewReasons"])),
    }
