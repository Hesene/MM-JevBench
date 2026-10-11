# MM-JevBench-10k 基线报告

本报告使用 `datasets/processed/10k/mmjevbench_10k.jsonl` 的 held-out `test` split。数据集共有 10,000 条 canonical records，其中 2,000 条 dev、8,000 条 test；本次 test 覆盖 5 个轨道和 6,468 个独立 `group_id`。

## 1. 评测口径

评测器同时报告两类估计量：

- **Sample mean**：每条 canonical record 等权；
- **Group macro**：先在同一 `group_id` 内平均，再让每个 group 等权。

Group macro 对 OmniGUI 尤其重要，因为同一 episode 含多个 step。它也避免共享材料的多题组因题目数较多而不成比例地支配 Accuracy、NLL 和 multiclass Brier sum。现有 sample-level 字段保持不变，新增结果位于每个 track 的 `group_macro`，跨轨道等权结果位于 `equal_track_group_macro`。

当前 Wilson 区间仍是 sample-level 二项区间。正式模型比较应按 `group_id` 做 paired group bootstrap，不能把同一 episode 或共享材料内的记录视为独立样本。

## 2. Uniform baseline

Uniform baseline 对每个候选给出相同概率。候选并列时评测器确定性选择首个候选，因此 Accuracy 反映第一选项标签频率，而不是随机抽样准确率。

| Track | Test records | Groups | Acc. | Group Acc. | NLL | Group NLL | Brier | Group Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| academic_cmmmu | 608 | 600 | 0.2582 | 0.2592 | 1.2974 | 1.2973 | 0.7179 | 0.7179 |
| culture_ccbench | 408 | 404 | 0.2206 | 0.2203 | 1.3863 | 1.3863 | 0.7500 | 0.7500 |
| exam_multi | 3,995 | 3,995 | 0.2476 | 0.2476 | 1.3043 | 1.3043 | 0.7204 | 0.7204 |
| general_mmbench | 931 | 895 | 0.3394 | 0.3439 | 1.3074 | 1.3060 | 0.7232 | 0.7227 |
| gui_action_type | 2,058 | 574 | 0.1166 | 0.0923 | 2.5649 | 2.5649 | 0.9231 | 0.9231 |
| **Equal-track macro** | — | — | **0.2365** | **0.2327** | **1.5721** | **1.5718** | **0.7669** | **0.7668** |

其他 equal-track sample-level 指标：chance-corrected Accuracy `0.0026`、ECE-10 `0.0627`、AURC `0.7304`。缺失或非法预测为 `0/8,000`。

## 3. Dev label-position prior baseline

该基线只使用 dev split，按 `(track, candidate_count)` 统计 gold 的候选位置频率，并进行 `alpha=1` 的 Laplace smoothing；它不读取 test 标签。

| Track | Test records | Groups | Acc. | Group Acc. | NLL | Group NLL | Brier | Group Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| academic_cmmmu | 608 | 600 | 0.3339 | 0.3317 | 1.2927 | 1.2932 | 0.7116 | 0.7121 |
| culture_ccbench | 408 | 404 | 0.2843 | 0.2871 | 1.3825 | 1.3822 | 0.7481 | 0.7479 |
| exam_multi | 3,995 | 3,995 | 0.2999 | 0.2999 | 1.2996 | 1.2996 | 0.7181 | 0.7181 |
| general_mmbench | 931 | 895 | 0.3416 | 0.3450 | 1.2958 | 1.2915 | 0.7182 | 0.7165 |
| gui_action_type | 2,058 | 574 | 0.5194 | 0.5151 | 1.3633 | 1.3053 | 0.6436 | 0.6335 |
| **Equal-track macro** | — | — | **0.3558** | **0.3558** | **1.3268** | **1.3144** | **0.7079** | **0.7056** |

其他 equal-track sample-level 指标：chance-corrected Accuracy `0.1430`、ECE-10 `0.0479`、AURC `0.6087`。缺失或非法预测为 `0/8,000`。

## 4. 解读

Dev prior 相比 uniform 的 equal-track Accuracy 提高约 `11.93` 个百分点，group-macro Accuracy 提高约 `12.31` 个百分点。增益主要由 `gui_action_type` 的动作类别不平衡驱动：仅依赖 dev 标签位置先验即可达到约 51.5% 的 group-macro Accuracy。因此，GUI 模型必须同时与这个先验基线比较，不能只与 13 类 uniform chance 比较。

这两套基线是数据和评测链路的 smoke test，不是论文中的多模态模型结果。论文主实验仍需冻结 prompt、记录概率来源，并同时报告 sample mean、group macro、各轨道结果以及 group-aware 置信区间。

## 5. 产物

- `predictions/10k/uniform.jsonl`
- `predictions/10k/dev_prior.jsonl`
- `reports/baselines/10k/uniform.json`
- `reports/baselines/10k/dev_prior.json`

