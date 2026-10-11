# MM-JevBench 10k Cross-source Deduplication Audit

- Input: `E:\Codex\MM-JevBench\datasets\processed\10k\mmjevbench_10k.jsonl`
- Input SHA-256: `d0dbcafaab30baec4deed99fefa72f033fdc1a7fde934aeea2fdd15a8a7b4ce1`
- Generated (UTC): 2026-10-11T17:57:49.208820+00:00
- Verdict: **NO MUST-FIX EXACT LEAKAGE FOUND**
- Data mutation: **none**

## Summary

| Metric | Count |
| --- | --- |
| Records | 10000 |
| Readable / referenced images | 10689 / 10689 |
| Missing / unreadable images | 0 / 0 |
| Exact decision-text groups | 0 |
| Exact question-only groups | 0 |
| Exact image SHA groups | 0 |
| Must-fix exact leakage pairs | 0 |
| Near-text review candidates (reported) | 166 |
| Near-image review candidates (reported) | 0 |

## Source inventory

| Source | Records |
| --- | --- |
| CCBench | 510 |
| CMMMU | 760 |
| MMBench-Dev-CN | 1164 |
| MULTI-Benchmark | 4994 |
| OmniGUI | 2572 |

## Must-fix exact leakage

No cross-source pair simultaneously shares an exact normalized decision signature and exact image bytes. Text-only, image-only, and approximate matches remain review candidates and were not deleted.

_None._

## Exact decision-text groups

_None._

## Exact image SHA groups

_None._

## Priority near-text candidates

_None._

## Priority near-image candidates

_None._

## Interpretation and limits

- `decision-text exact` compares normalized context + question + an order-insensitive candidate set. Question-only exact groups are reported separately because generic templates are not sufficient evidence of leakage.
- `image exact` uses file-byte SHA-256. `must-fix` is intentionally conservative: the same cross-source record pair must share both an exact decision-text signature and an exact image SHA.
- Near text uses rare character-trigram and SimHash blocking, then SequenceMatcher and trigram Jaccard scoring. Each reported text candidate also includes the closest available image-hash evidence. Near images require pHash agreement (alone or jointly with dHash), so sparse-image dHash collisions are suppressed. These are candidate generators, not deletion rules.
- Oversized perceptual-hash/text buckets are skipped to keep the 10k audit tractable; exact hashing is exhaustive for every readable image.
- Missing media are listed in the JSON report. They reduce near/exact image coverage only for those paths; the underlying dataset is not modified.
