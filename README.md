# MM-JevBench

MM-JevBench 是一个面向**多模态候选式概率决策模型**的可扩展评测仓库。模型读取图像、文本、音频、视频或 GUI 历史状态，并对预先声明的候选决策输出完整概率分布。

当前冻结版本为 `MM-JevBench-10k-v1.0`。它评估两类互补能力：

1. **任务有效性**：Accuracy、概率校准、选择性预测、模态消融与效率；
2. **决策一致性**：候选重排、批处理、概率测度、逻辑单调性和候选删除是否满足 Jev 关系。

## 当前发布

| Track | 来源 | Canonical | Dev | Test | Groups |
|---|---|---:|---:|---:|---:|
| Academic reasoning | CMMMU | 760 | 152 | 608 | 752 |
| Chinese exam reasoning | MULTI v1.3.1 | 4,994 | 999 | 3,995 | 4,994 |
| GUI action-type decision | OmniGUI | 2,572 | 514 | 2,058 | 708 |
| General multimodal reasoning | MMBench-Dev-CN | 1,164 | 233 | 931 | 1,121 |
| Chinese culture reasoning | CCBench | 510 | 102 | 408 | 504 |
| **合计** | **5 个来源** | **10,000** | **2,000** | **8,000** | **8,079** |

主文件：`datasets/processed/10k/mmjevbench_10k.jsonl`。

- JSON Schema 与 release-level 校验已通过；
- 旧版 1,500 条三轨 anchor 的 ID 和 split 100% 保留；
- 所有 canonical 子项与派生变体均按 `group_id` 防止跨 split 泄漏；
- 15,718 个 release 引用媒体全部存在，缺失 0；
- 当前设计不包含安全内容轨道，也不应据此声称评测了模型安全能力。

三轨兼容子集位于 `datasets/processed/10k/mmjevbench_10k_public8000.jsonl`，包含 CMMMU、MULTI 与 OmniGUI 共 8,000 条。它用于兼容旧三轨分析，不是五轨主榜的替代品。

## Jev coherence suite

只从 8,000 条 held-out test canonical cases 生成关系变体：

| Family | Relations |
|---|---:|
| REP | 22,754 |
| BAT | 1,000 |
| MEA | 15,377 |
| LOG | 8,000 |
| CHO | 7,377 |
| **合计** | **54,508** |

变体文件共有 61,508 条。它们是依赖于 canonical parent 的关系测试，**不计入 10,000 条 canonical 总量**。

> GitHub 发布说明：主 10k JSONL、关系定义、媒体 manifest 和构建代码进入仓库；约 6.1 GB 的来源媒体不进入 Git。`datasets/coherence/10k/variants.jsonl` 大于 GitHub 单文件上限，也不进入 Git，可使用下方命令从 canonical 数据确定性重建。

## 为什么它不是旧数据的简单拼接

- eligibility、版本、抽样框、分层、group 和 split 在模型实验前冻结；
- CMMMU 纳入有公开 gold 的单选与判断题，并将共享媒体题绑定到同一 group；
- MULTI 按 `subject × image_bin × Elite` 分层，从唯一 problem group 中确定性抽样；
- OmniGUI 纳入全部 2,572 个合法步骤，但 708 个 episode 是推断与切分单元；
- MMBench-Dev-CN 与 CCBench 排除 CircularEval 的旋转副本，只保留 canonical pass；
- 1,500 条旧 anchor 严格嵌套，避免扩容后悄然更换已报告样本；
- 主结果按五轨等权宏平均，同时报告逐轨结果；不把任意样本配比的 micro score 解释为现实总体。

详细抽样与统计口径见 `docs/sampling_protocol_10k.md`。

## 目录

```text
configs/                       冻结版本、来源与 10k 抽样配置
convert/                       来源转换器
datasets/processed/10k/        10k canonical release
datasets/media/                媒体文件（通常不提交 Git）
datasets/coherence/10k/        10k coherence 变体与关系
datasets/manifests/            媒体、来源和抽样清单
docs/                          数据卡、抽样、构建与论文方案
mmjevbench/                    schema、抽样、校验和指标实现
schemas/                       JSON Schema
scripts/                       合并、校验、下载和审计入口
tests/                         单元与不变量测试
```

## 环境

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

## 输入版本

- CMMMU：固定 Hugging Face revision 的 dev + val，有公开答案；
- MULTI：`MULTI_v1.3.1_20251016_release.zip`；
- OmniGUI：固定 revision 的 `merged_sorted.json` 与对应媒体；
- MMBench-Dev-CN、CCBench：`open-compass/MMBench@8eaac9ae42e22eaf42863b218455acd51268ba1c`。

具体字段、规模、许可边界和风险见 `docs/data_sources.md`。原始来源的内容许可并不因统一 schema 而变成单一软件许可。

## 合并与验证

五轨输入转换完成后，使用冻结配置合并：

```powershell
.\.venv\Scripts\python scripts\merge_10k_release.py `
  datasets\processed\10k\cmmmu_760.jsonl `
  datasets\processed\10k\multi_4994.jsonl `
  datasets\processed\10k\omnigui_2572.jsonl `
  datasets\processed\10k\mmbench_dev_cn_1164.jsonl `
  datasets\processed\10k\ccbench_510.jsonl `
  --output datasets\processed\10k\mmjevbench_10k.jsonl `
  --expect 10000
```

```powershell
.\.venv\Scripts\python scripts\validate_dataset.py `
  datasets\processed\10k\mmjevbench_10k.jsonl
```

`scripts/merge_10k_release.py` 会验证逐轨配额、总量、schema、anchor ID 与 split 保留情况；失败时不应发布输出。

## 构建 coherence suite

```powershell
.\.venv\Scripts\python scripts\build_coherence_suite.py `
  datasets\processed\10k\mmjevbench_10k.jsonl `
  --variants-output datasets\coherence\10k\variants.jsonl `
  --relations-output datasets\coherence\10k\relations.jsonl `
  --permutations 3
```

关系定义、适用前提和误差公式见 `docs/coherence_protocol.md`。

## 导出 Hugging Face 数据包

GitHub 只保存代码、冻结 JSONL、关系和 manifest。可用下面的命令生成适合 Hugging Face Dataset Viewer 的 `dev.parquet`、`test.parquet` 与数据卡：

```powershell
.\.venv\Scripts\python scripts\export_hf_dataset.py
```

输出位于 `dist/huggingface/`，不包含来源媒体。发布媒体前必须逐来源确认再分发许可和隐私要求。

## 核心指标

- Accuracy、balanced/macro diagnostics 与 chance-corrected Accuracy；
- NLL、multiclass Brier、equal-mass ECE、classwise ACE；
- risk-coverage curve 与 AURC；
- modality ablation gap；
- REP/BAT/MEA/LOG/CHO coherence error；
- invalid-output rate；
- 以 `group_id` 为重采样单元的分层 bootstrap 95% CI；
- OmniGUI 的 episode-macro 与 step-micro 指标；
- latency p50/p95、throughput 和成本，单独报告，不与质量混为单一分数。

## 当前完成边界

10k canonical 与 coherence suite 已生成，但以下工作尚未完成：

- 10,000 条全量人工内容审查、模态必要性双人标注和第三人裁决；
- 五来源全量跨源近重复人工复核；
- 论文级 VLM、omni-modal、GUI agent 与 decision-model 实验矩阵；
- 新采集或 sealed test，以缓解公开 benchmark 的训练污染；
- 发布前的许可、隐私和媒体再分发审查。

因此当前产物是可复现的**论文级评测基础设施和冻结数据版本**，不是已经完成全部人工验证和模型实证的投稿成稿。

## 文档

- `docs/sampling_protocol_10k.md`：10k 抽样、嵌套、切分与统计推断；
- `docs/build_report_10k.md`：本次 10k 实际构建与校验；
- `docs/dataset_card.md`：用途、组成、伦理和限制；
- `docs/data_sources.md`：来源版本、字段和许可风险；
- `docs/coherence_protocol.md`：五类 Jev 一致性关系；
- `reports/cross_source_dedup_10k.md`：五来源跨源去重审计；
- `docs/paper_blueprint.md`：研究问题、实验矩阵和论文表格；
- `BLOCKERS.md`：发布与论文实验仍需完成的事项。
