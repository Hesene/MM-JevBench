# 论文方案：MM-JevBench-10k

## 建议标题

**MM-JevBench: Benchmarking Calibrated and Coherent Multimodal Typed-Decision Models at 10K Scale**

中文工作题目：**MM-JevBench-10k：多模态候选式概率决策模型的准确性、校准性与一致性评测**

## 核心论点

现有多模态 benchmark 多数只问“答案是否正确”，而实际决策系统还需要输出完整候选概率、支持校准与拒答，并在语义等价或逻辑相关的决策请求之间保持自洽。MM-JevBench-10k 将多模态证据、typed decision、group-aware 推断与 Jev coherence 放入同一冻结协议。

当前版本覆盖五类任务：学术推理、中文考试推理、GUI 动作类别、通用图文推理和中国文化图文推理。它不包含安全内容轨道，论文不得声称已评测模型安全能力。

## 研究问题

- **RQ1 Accuracy/Calibration**：不同 VLM、omni-modal model 和 decision adapter 的概率是否准确且可校准？
- **RQ2 Modality contribution**：full multimodal 相比 text-only、OCR/caption 和单模态输入有多大增益？
- **RQ3 Coherence**：候选置换、批处理、否定/合并、逻辑包含和候选删除是否满足 REP/BAT/MEA/LOG/CHO？
- **RQ4 Efficiency**：不同概率提取方法的质量、延迟、吞吐、成本和 invalid rate 构成怎样的 Pareto frontier？
- **RQ5 GUI decision**：通用 VLM、omni-modal model 与 GUI agent 在 action primitive 和开放动作指标之间有何差异？
- **RQ6 Scale and diversity**：模型排名是否会在旧 1,500 条 anchor、三轨 8,000 条子集和五轨 10,000 条主榜之间改变？

## 可主张的贡献

1. 一个 10,000 条、五轨、统一候选概率接口的中文/多模态决策 benchmark；
2. 严格保留 1,500 条旧 anchor 的扩容方法，避免版本升级后隐式换题；
3. 以 8,079 个 group 为统计基础的 split、bootstrap 和泄漏控制协议；
4. 61,508 条变体、54,508 个关系定义的多模态 Jev coherence suite；
5. 区分 native、token-logprob-derived 与 verbalized probability 的统一评测框架；
6. 联合报告 accuracy、calibration、selective risk、coherence、modality contribution 和 efficiency。

在完成人工审查和模型实验前，不能声称数据“无错误”、模型排名已验证或 benchmark 已证明真实部署泛化。也不能声称“首个所有多模态决策 benchmark”。

## 数据设计摘要

| Track | Records | Groups | 设计角色 |
|---|---:|---:|---|
| CMMMU | 760 | 752 | 有公开 gold 的单选+判断 census |
| MULTI | 4,994 | 4,994 | 学科×图像数×Elite 分层抽样 |
| OmniGUI | 2,572 | 708 | 全 step census，episode 聚类 |
| MMBench-Dev-CN | 1,164 | 1,121 | 排除 CircularEval 副本后的 census |
| CCBench | 510 | 504 | 排除 CircularEval 副本后的 census |

Dev/test 为 2,000/8,000。所有 prompt、parser、temperature 和拒答阈值只能在 dev 上确定。

## 最低实验矩阵

至少包括：

- uniform、dev label prior 与 majority/action prior；
- text-only，不使用 OCR；
- text + OCR/caption adapter；
- 两个开源 VLM 家族，最好包含不同规模；
- 一个可原生处理音频/视频的 omni-modal model；
- 一个 Jev/OpenJev/Chinese-Jev 类型 decision model，经 OCR/caption adapter 接入；
- 一个 GUI-agent 专用模型；
- 有预算时加入强闭源多模态模型作为参考上界。

每个模型同时报告 raw probability 与只在 dev 上拟合的 calibrated probability。概率来源必须标记为：

- `native`：模型原生概率接口；
- `logprob-derived`：从候选 token logprob 构造；
- `verbalized`：模型以文本陈述概率。

三种来源不能在同一排行中不加说明地混用。

## 输入与消融条件

预注册以下输入条件：

- text-only，不运行 OCR；
- text + OCR；
- image/pixels + text；
- image + text + OCR；
- OmniGUI 额外比较 no-audio、no-video、no-audio-video 与 full；
- history ablation 只适用于明确依赖历史的 GUI case。

“输入中有图”不等于“图像对 gold 必要”。模态必要性结论必须基于人工标签或严格反事实，不可仅由单一模型消融失败反推。

## 主表设计

### Table 1：数据组成

Track、source revision、sampling frame、eligible、canonical、dev/test、group 数、候选数、媒体类型、人工审查覆盖。

### Table 2：主任务

逐轨报告 Accuracy、chance-corrected Accuracy、NLL、Brier、ECE/ACE、AURC、invalid rate 和 95% group-bootstrap CI；最后给五轨等权 macro。

### Table 3：模态贡献

比较 text-only、OCR/caption、pixels、full multimodal；OmniGUI 加 audio/video/history 消融。只在人工确认的 dependency subgroup 上做强因果式表述。

### Table 4：Coherence

分别报告 REP/BAT/MEA/LOG/CHO 的平均误差、pass@0.05、invalid rate 和 group-bootstrap CI。不能与任务 Accuracy 合成单一“智能分”。

### Table 5：GUI action

同时报告 step-micro、episode-macro、逐动作类别结果，以及可用时的官方开放动作指标。明确 action-type Choice 与原任务并不等价。

### Table 6：效率

硬件、模型版本、输入分辨率、batch size、p50/p95、throughput、显存和成本。网络 API 与本地推理分表。

### Table 7：规模与来源敏感性

比较 1,500 anchor、三轨 8,000 子集与五轨 10,000 主榜，报告排名变化和 paired effect，而不是把不同版本分数直接混为同一总体。

## 统计分析

- 主 headline 为五轨等权 macro；
- 所有主 CI 使用至少 10,000 次 track/stratum 分层的 group bootstrap；
- 模型差异在相同 bootstrap draw 上配对；
- OmniGUI 以 episode 为 group，主报 episode-macro；
- coherence 以 canonical parent/group 聚类；
- ECE 使用 equal-mass bins 并给 bootstrap CI；
- subgroup `n_groups < 100` 只作探索性描述；
- 多重比较使用 Holm correction；
- missing、parse failure 和非法概率一律计错并报告 coverage；
- latency 与质量不合成任意权重总分。

## 污染与有效性实验

所有来源都是公开 benchmark 或公开材料，因此必须把训练污染作为核心限制，而非脚注。建议：

1. 收集模型自报训练截止时间与可能使用的数据；
2. 对题干、候选、图片 hash 做公开语料近邻搜索；
3. 比较公开题与新采集/sealed 子集；
4. 单独报告 source-retrieval 或 memorization probes；
5. 不将高分直接解释为真实世界 decision quality。

## 投稿前仍需完成

1. OmniGUI 全媒体物化及最终 manifest/hash 审计；
2. 10,000 条人工题目—媒体—候选—gold 快速审查；
3. modality dependency 双人标注与第三人裁决；
4. 五来源跨源文本/图像近重复复核；
5. 完整 baseline 矩阵、冻结 prompt/parser 和 dev-only 校准；
6. 20%–30% 新采集或 sealed test，或对缺失部分作明确限制；
7. conversion fidelity study：统一 schema 与来源原指标的一致性；
8. 许可、隐私、媒体再分发和伦理审查；
9. 发布数据卡、模型卡式结果说明、失败案例和复现脚本。

## 论文叙事边界

推荐将论文主张限定为“构建并验证一个 group-aware 的多模态概率决策评测协议”，而不是声称 10k 数量本身带来外部有效性。真正有说服力的证据来自：冻结设计、嵌套复现、人工质量记录、group-aware CI、模型矩阵和 sealed 数据表现。
