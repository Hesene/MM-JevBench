---
pretty_name: MM-JevBench
language:
- zh
- en
task_categories:
- visual-question-answering
- image-classification
- other
size_categories:
- 10K<n<100K
---

# MM-JevBench

MM-JevBench is a multimodal benchmark for calibrated candidate-based decision-making, robustness, and cross-modal coherence. The frozen v1.0 release contains 10,000 canonical records: 2,000 development records and 8,000 held-out test records across CMMMU, MULTI, OmniGUI, MMBench-Dev-CN, and CCBench.

The hosted Parquet files contain normalized records, source identifiers, group-aware splits, candidates, gold labels, probability targets, and media manifests. Source media are not redistributed in this repository. Reconstruct them from the upstream datasets with the code and pinned revisions in the companion GitHub repository.

## Tracks

| Track | Records |
|---|---:|
| Academic visual reasoning | 760 |
| Chinese examination reasoning | 4,994 |
| GUI action-type decision | 2,572 |
| General multimodal reasoning | 1,164 |
| Chinese cultural reasoning | 510 |

All canonical tasks are closed-world choices. Gold outcome distributions are currently one-hot source labels; evaluated models should return a probability distribution over every candidate. The primary metrics include Accuracy, NLL, multiclass Brier score, calibration error, selective risk, and group-aware coherence diagnostics.

## Important limitations

- The five upstream benchmarks are public and may occur in model training corpora.
- Source media have separate licenses and redistribution conditions.
- OmniGUI steps from the same episode are dependent; use episode/group-macro estimates and group-level bootstrap confidence intervals.
- Automated validation is complete, but full human semantic review and paper-scale model experiments remain future work.

See the companion repository for the full dataset card, source audit, sampling protocol, schema, hashes, conversion scripts, and evaluation code: https://github.com/Hesene/MM-JevBench
