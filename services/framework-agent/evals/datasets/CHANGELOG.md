# Benchmark Dataset Changelog

## agent-benchmark-v1 — 2026-09-28

- Initial frozen release: 120 cases.
- Categories: 25 Menu, 25 RAG, 20 Action, 20 Multi-turn, 20 Safety, 10 Smalltalk/Ambiguous.
- Split: 80 Dev, 40 Holdout; complete multi-turn conversations remain within one split.
- Golden E2E projection: 25 cases.
- Frozen hashes are recorded in `benchmark-manifest-v1.json`.

V1 must not be silently edited. A factual correction requires an explicit entry here and refreshed
manifest hashes; semantic expansion should create V2.
