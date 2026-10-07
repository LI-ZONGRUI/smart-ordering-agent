# Benchmark Dataset Changelog

## agent-benchmark-v1 — 2026-09-28

- Initial frozen release: 120 cases.
- Categories: 25 Menu, 25 RAG, 20 Action, 20 Multi-turn, 20 Safety, 10 Smalltalk/Ambiguous.
- Split: 80 Dev, 40 Holdout; complete multi-turn conversations remain within one split.
- Golden E2E projection: 25 cases.
- Frozen hashes are recorded in `benchmark-manifest-v1.json`.

V1 must not be silently edited. A factual correction requires an explicit entry here and refreshed
manifest hashes; semantic expansion should create V2.

## Hybrid Router Holdout v2 — 2026-10-07

- Holdout v1 was formally evaluated once at 33/40 (82.50%) and then used for post-hoc failure analysis. It is now a regression and failure-analysis set, not a fully unseen final test.
- Added a separate 40-case, route-only Holdout v2 from the documented Routing Contract, before any Router v2 production changes. Its file and SHA-256 freeze are recorded in `holdout-v2-manifest.json`.
- V2 has 8 Menu, 8 RAG, 7 Action, 8 Multi-turn, 7 Safety and 2 Smalltalk/Ambiguous cases. It is not a replacement projection of `agent-benchmark-v1.jsonl`; the original 120 cases and manifest remain frozen.
- V2 has not been evaluated. Do not inspect its cases to tune Router v2. A future change to this dataset requires a new holdout version.
