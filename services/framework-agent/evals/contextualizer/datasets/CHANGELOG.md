# Contextualizer Benchmark Dataset Changelog

## v1 — 2026-10-07

- Created the 40-case Contextualizer-only dataset with a 30 Dev / 10 Holdout split.
- Covered all eight fixed language-phenomenon categories.
- Froze the canonical dataset and both projections with SHA-256 in `manifest.json`.
- Reserved Holdout for a future explicitly confirmed evaluation; it was not run in this phase.

V1 is immutable. Correcting data requires a documented new dataset version and new hashes; tuning
the production Prompt or parser from frozen Holdout content is prohibited.

