# MM-JevBench-10k 抽样与统计分析协议

冻结版本：`MM-JevBench-10k-v1.0`  
冻结日期：2026-10-12  
随机种子：`MM-JevBench-10k-v1.0`

## 1. 研究对象与设计原则

MM-JevBench-10k 的目标不是估计“互联网上所有多模态任务”的自然占比，而是构造一个覆盖不同决策结构的、可复现的诊断性 benchmark。所有 eligibility、抽样、分组和切分规则应在运行待评模型前冻结。

预注册研究问题为：

1. 模型能否做出正确的多模态候选决策；
2. 模型给出的完整候选概率能否被校准，并支持选择性预测；
3. 图像、音频、视频、OCR 或历史状态是否对决策产生可验证的增量贡献；
4. 概率是否满足 REP、BAT、MEA、LOG、CHO 五类 Jev 一致性；
5. 通用多模态模型与 GUI agent 在动作类别决策上有何差异。

必须区分三个 estimand：

- **Benchmark estimand**：五个 track 等权宏平均，是主榜 headline；
- **Track estimand**：各 track 内按冻结设计计算的性能；
- **Item micro score**：10,000 条记录直接平均，仅作描述，不能解释为现实任务分布。

当抽样比例不等于来源总体比例时，另报告按 `sampling.analysis_weight` 计算的 Hájek 标准化结果。

## 2. 总体组成

| Track | Canonical | Dev | Test | Groups | 抽样角色 |
|---|---:|---:|---:|---:|---|
| CMMMU | 760 | 152 | 608 | 752 | 有效单选与判断题 census |
| MULTI | 4,994 | 999 | 3,995 | 4,994 | 分层、唯一 problem group 抽样 |
| OmniGUI | 2,572 | 514 | 2,058 | 708 | 合法 step census，episode 聚类 |
| MMBench-Dev-CN | 1,164 | 233 | 931 | 1,121 | canonical pass census |
| CCBench | 510 | 102 | 408 | 504 | canonical pass census |
| **合计** | **10,000** | **2,000** | **8,000** | **8,079** | — |

按 split 计，dev 含 1,611 个 group，test 含 6,468 个 group。记录数大于 group 数的 track 不能把同组记录当作独立观测。

## 3. Anchor 嵌套

旧版三轨 1,500 条样本是冻结 anchor：

```text
MM-JevBench-mini-v1.0-public3 ⊂ MM-JevBench-10k-v1.0
```

扩展时满足以下不变量：

- 1,500 个 anchor ID 全部存在；
- 1,500 个 anchor split 全部保持不变；
- 不因模型表现、题目难度或后验观察替换 anchor；
- 新增同组记录继承既有 group 的 split；
- coherence 和鲁棒性变体不计入 canonical 总数。

这一设计支持与早期实验做严格纵向比较，也避免扩容后通过换题获得虚假提升。

## 4. 通用 eligibility

所有 canonical 记录必须满足：

- 至少包含一种非纯文本媒体；
- 有可追溯的来源 gold；
- 候选完整，gold 与候选索引一致；
- 媒体引用指向预期来源，并在发布前通过存在性、解码和哈希审计；
- 不包含文件名、元数据或解析残留形式的答案泄漏；
- 共享媒体、共享 parent problem、同一 episode 或明确近重复关系写入同一 `group_id`；
- 许可和隐私风险被记录，不能把统一 schema 误当作统一数据许可。

自动 eligibility 是进入人工审查队列的必要条件，不等价于人工确认题目无歧义。

## 5. 分来源设计

### 5.1 CMMMU：760

仅使用有公开答案的 dev + val。冻结排除表先移除 3 个经人工裁决的跨源重复或高风险近重复项。

构成为：

- 655 条有效单选题；
- 105 条判断题，其中来源答案“对”70 条、“错”35 条；
- 判断题映射为 `错误（错）` 与 `正确（对）` 两个候选；
- 共享媒体 hash 的题目保留，但必须绑定同一 group 和 split。

760 条记录对应 752 个 group。该轨为冻结 eligibility frame 的 census，来源框内 inclusion probability 为 1。判断题类别不平衡，因此除 Accuracy 外应报告 balanced accuracy、逐类 recall、NLL 与 Brier。

### 5.2 MULTI：4,994

使用固定的 v1.3.1 答案发布包。只纳入：

```text
question_type = 单选
AND image_count >= 1
AND options 可严格解析
AND source gold 指向现有候选
```

严格解析得到 5,784 条候选记录、5,583 个 problem group。本版本从中选取 4,994 个唯一 problem group，因此每个入选 group 只贡献一个 canonical case。

主要分层为：

```text
subject × image_bin(single/multiple) × MULTI-Elite
```

采用 capped square-root allocation，容量很小的层优先保留，随后按稳定 hash priority 抽样。多图与 Elite 是诊断性覆盖，不代表来源总体比例；必须同时报告设计平衡结果和来源加权结果。

### 5.3 OmniGUI：2,572

固定 release 实测为 708 episodes、2,572 个合法步骤。本版本纳入所有合法步骤，而不是每个 episode 只取一步。

- `group_id` 以 episode 为单位；
- 同一 episode 的所有 step 必须位于同一 split；
- action history 与媒体不得跨 split 泄漏；
- 主任务是 13 类 closed-world action primitive Choice；
- 原始结构化 action 继续保留，供官方开放动作指标使用。

由于 episode 长度不同，step-micro 会给长轨迹更大权重。论文主指标应采用 episode-macro，或令每个 step 权重为 `1 / episode_steps`；step-micro 作为补充。bootstrap 也必须以 episode 为重采样单元。

### 5.4 MMBench-Dev-CN：1,164

使用带公开 gold 的中文 dev 数据。CircularEval 通过对一个原题生成多个候选旋转版本来降低答案位置偏差；这些旋转不是独立语义题。本版本只保留 `index < 1,000,000` 的 canonical pass，排除旋转副本。

有效 frame 为 1,164 条、1,121 个媒体 group，全部纳入。描述性分层为 `category × l2_category`。共享图像样本按媒体 hash 绑定同一 split。

### 5.5 CCBench：510

同样只保留 canonical pass，排除 CircularEval 旋转副本。有效 frame 为 510 条、504 个媒体 group，全部纳入。描述性分层为 category，并保持共享媒体 group 不跨 split。

CCBench 重点覆盖中国文化、文物、传统表演、书画、景观建筑、服饰饮食和历史人物。文化知识随地区、时代与标注口径变化，错误分析需避免把单一来源 gold 扩张为普遍文化判断。

## 6. 确定性抽样与 split

稳定优先级由冻结 seed、来源、source ID、group ID 和 namespace 计算。输入文件排序变化不得改变结果。

split 满足：

- 总量严格为 dev 2,000、test 8,000；
- anchor split 优先保留；
- 新 group 按 track/stratum 做确定性分配；
- 一个 group 只能属于一个 split；
- 所有后生成的变体继承 parent split；
- dev 可用于 prompt、解析器、阈值和温度缩放；test 只用于冻结后的最终评测。

不得根据 test 结果重新选择样本、修改 prompt、重拟温度或重新定义 parse rule。

## 7. Coherence 关系抽样

关系只从 8,000 条 test canonical cases 生成：

| Family | Relations |
|---|---:|
| REP | 22,754 |
| BAT | 1,000 |
| MEA | 15,377 |
| LOG | 8,000 |
| CHO | 7,377 |
| **合计** | **54,508** |

对应 61,508 条变体。关系行与变体行不是独立 benchmark cases；统计时以 canonical parent/group 聚类，不能用 61,508 作为独立样本量计算置信区间。

## 8. 主指标与推断

### 8.1 主报告

- 每轨 Accuracy、NLL、multiclass Brier、equal-mass ECE、classwise ACE、AURC、invalid rate；
- 五轨等权 macro；
- 每轨与关键预注册 subgroup；
- OmniGUI episode-macro 与 step-micro；
- REP/BAT/MEA/LOG/CHO 分开报告，不与 Accuracy 合成任意总分。

### 8.2 置信区间

主 CI 使用至少 10,000 次 stratified group bootstrap：

1. 在 track 和预注册 stratum 内抽取 `group_id`；
2. 抽中 group 后带入其全部记录；
3. 同一 bootstrap draw 同时计算所有模型，得到 paired difference；
4. 对 OmniGUI 以 episode 聚类；
5. 对 coherence 以 canonical parent/group 聚类。

报告 point estimate、95% CI、paired effect 与实际有效 group 数。不能用 8,000 个 test records 的普通独立二项区间替代 group-aware CI。

### 8.3 多重比较

- subgroup `n_groups < 100` 只作探索性描述；
- 多 subgroup 假设检验采用 Holm correction；
- 排名相近时报告 paired CI，而不是仅比较小数点后三位；
- missing、parse failure 和非法概率输出计错，并单独报告 coverage。

## 9. 人工审查计划

当前尚未完成论文所需的全量人工审查。正式投稿前至少需要：

1. 对 10,000 条做媒体—题目—候选—gold 一致性审查；
2. modality dependency 由两人独立标注，第三人裁决；
3. 对共享媒体、跨源相似候选、解析异常和低质量图片全量复核；
4. 每个来源记录原始 agreement、Cohen's κ 或 Krippendorff's α；
5. critical defect 触发冻结 exclusion、同层 deterministic replacement 和版本升级；
6. 不允许根据待评模型是否答错决定删除样本。

机器校验、模型自评或 LLM-as-a-judge 不能替代上述人类审查。

## 10. 污染与外部有效性

五个来源均为公开 benchmark 或公开考试材料，强模型可能在预训练或指令微调中见过题目。CircularEval 去重、跨源哈希和文本相似度筛查只能缓解 release 内重复，不能证明模型未见过来源题。

论文必须：

- 报告来源发布日期和固定 revision；
- 对可能的数据污染作显式限制声明；
- 在条件允许时加入 20%–30% 新采集或 sealed test；
- 不把对公开旧题的高分解释为真实部署泛化；
- 对新加入的 MMBench/CCBench 与原三轨重新执行五来源跨源去重并人工裁决。

## 11. 冻结与版本升级

`MM-JevBench-10k-v1.0` 发布后，任何 gold、group、split 或 exclusion 变更都必须：

- 产生新版本号；
- 保留旧值、修改理由、证据与裁决者；
- 更新 manifest、数据哈希和构建报告；
- 重新运行 schema、媒体、去重与 split 审计；
- 不静默覆盖已用于论文结果的 release。
