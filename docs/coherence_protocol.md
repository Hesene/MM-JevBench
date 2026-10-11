# MM-JevBench 多模态决策概率一致性协议

## 1. 目的与报告边界

本协议评估模型给出的候选概率是否在**受控、语义保持或关系明确的成对样本**之间满足概率公理与决策一致性。它回答“模型的概率判断是否自洽”，不替代准确率、校准误差或多模态必要性评估。一个模型可能稳定地答错，也可能准确但不一致；论文中必须将 coherence 与 accuracy/calibration 分开报告。

所有主误差均采用总变差距离（total variation, TV）：

\[
d_{TV}(p,q)=\frac12\sum_i |p_i-q_i|\in[0,1].
\]

唯一例外是 CHO 的 log-odds 诊断，它无上界、以自然对数单位报告。任何未归一化、含 NaN/Inf 或超出 `[0,1]` 的输出都应记为 invalid，不可先静默归一化再评分。建议同时报告：有效样本数、invalid 率、均值、bootstrap 95% 置信区间，以及按来源、任务、模态组合和难度的分层结果。

## 2. 五类关系总览

| 代码 | 名称 | 核心问题 | 主误差 |
|---|---|---|---|
| REP | Representation equivariance | 只改变候选表示/顺序，概率是否随候选正确对齐？ | 对齐后的 TV |
| BAT | Batch independence | 同一样本单独推理与批量推理时，分布是否不受邻居样本影响？ | 样本级 TV 的均值 |
| MEA | Probability-measure algebra | 否定是否取补集、互斥事件合并是否满足有限可加性？ | complement/merge TV |
| LOG | Logical monotonicity | 若命题 A 蕴含 B，是否满足 `P(A) ≤ P(B)`？ | 正向违反间隙均值 |
| CHO | Choice-set consistency | 删除未保留候选后，保留候选的条件概率和相对赔率是否稳定？ | conditional TV；pairwise log-odds change |

关系标签建议写入变体记录，例如 `coherence.relation = "REP"`，并用 `parent_id` 或 `relation_group_id` 关联同组观测。所有变换必须在 split 之后进行，同一关系组只能出现在一个 split 中。

## 3. REP：候选表示等变性

### 3.1 适用前提

- 变换前后多模态证据、问题、候选语义和候选集合完全相同；
- 只重排候选，或替换不改变语义与语用强度的稳定候选 ID；
- prompt 不包含“优先第一个”等位置提示，且没有把位置编码为动作含义；
- action 任务若动作顺序本身具有执行语义，不适用本关系。

### 3.2 变换

对候选集合施加由固定随机种子产生的置换 `π`。至少生成一个非恒等置换；候选数允许时，建议为每个 canonical 样本生成 2 个置换。保存 `new_to_reference`：新位置 `j` 对应原位置 `π(j)`。

### 3.3 误差

先用逆对齐把变体概率放回原候选坐标，再计算 TV：

\[
E_{REP}=d_{TV}(p,\operatorname{align}(p^{\pi},\pi)).
\]

`0` 表示完全等变，`1` 表示最大分歧。实现接口：

```python
candidate_permutation_alignment_error(reference, permuted, new_to_reference)
```

## 4. BAT：批次独立性

### 4.1 适用前提

- 单条与批量运行使用相同模型、prompt 模板、媒体预处理、解码与数值精度；
- 样本未被截断，批量 padding/mask 正确；
- 对随机模型，应固定随机种子，或先以重复运行估计自然方差；
- 只将彼此无关的样本组成 batch；不得把多轮上下文当作普通 batch。

### 4.2 变换

先逐条运行样本，再把同一批样本按预注册的 batch size 与顺序共同运行。为了检测位置效应，建议轮换 batch 位置，并加入不同长度和不同模态组合的邻居。使用稳定 sample ID 对齐，不能依赖异步返回顺序。

### 4.3 误差

对每个样本计算独立分布与批量分布的 TV，主指标取宏平均：

\[
E_{BAT}=\frac1N\sum_n d_{TV}(p_n^{ind},p_n^{batch}).
\]

同时可报告最大值作为工程诊断。实现接口：

```python
batch_independent_distribution_error(independent, batched, reduction="mean")
```

## 5. MEA：概率测度代数

### 5.1 Noul 否定/补集

#### 适用前提

- Noul 候选固定为 `[否, 是]`；
- 变体命题是原命题的**精确逻辑否定**，不能混入反义、程度变化、时态变化或双重否定；
- 两次询问共享完全相同的多模态证据和指代范围；
- 对含“不确定/未知”第三状态的任务，二元补集关系不成立，不应使用该测试。

#### 变换与误差

把命题 `S` 改为 `¬S`。若原分布为 `[p(¬S), p(S)]`，则否定提示的期望分布是 `[p(S), p(¬S)]`：

\[
E_{MEA-neg}=d_{TV}([p(S),p(\neg S)],p_{prompt(\neg S)}).
\]

实现接口：

```python
noul_negation_error(proposition, negated_proposition)
```

### 5.2 Choice 合并/有限可加性

#### 适用前提

- 原候选互斥且穷尽；
- 每个合并候选恰好代表若干原候选的析取，组间不重叠且完整覆盖原集合；
- 合并文字不增加解释、价值判断或显著性；
- gold 与人工审校确认合并前后事件边界一致。

#### 变换与误差

将 fine candidates 按分区 `G_1,...,G_K` 合并。概率有限可加性要求：

\[
q_k^*=\sum_{i\in G_k}p_i,\qquad
E_{MEA-merge}=d_{TV}(q^*,q^{model}).
\]

实现接口：

```python
choice_merge_additivity_error(fine_distribution, groups, merged_distribution)
```

## 6. LOG：逻辑单调性

### 6.1 适用前提

- 在相同证据与量词范围下，命题 A 在逻辑上蕴含 B；
- 蕴含边由规则、知识图谱或至少两名标注者复核，不能只凭常识相似度建立；
- 命题不能因措辞带来额外语用暗示；
- 使用每个 Noul `[否, 是]` 分布中的 `P(是)`；
- 若命题依赖不同图像区域，应确认两个问题引用的是同一个实体与时刻。

### 6.2 变换与误差

在同一关系组中询问 A 与 B。对每条蕴含边 `A → B`，定义违反间隙：

\[
v(A,B)=\max(0,P(A)-P(B)).
\]

主误差为全部预注册蕴含边的 `v` 均值，并同时报告违反率 `mean(v > τ)`；`τ` 只用于违反率的数值容差，不能用来降低主误差。

```python
logical_monotonicity_error(yes_probabilities, implications)
logical_monotonicity_violations(yes_probabilities, implications, tolerance=0.0)
logical_monotonicity_violation_rate(yes_probabilities, implications, tolerance=0.0)
```

## 7. CHO：子菜单条件概率与赔率一致性

### 7.1 适用前提

CHO 比纯概率公理更强，依赖稳定偏好/无关选项独立性（IIA）假设，只能用于以下受控项目：

- 从原 Choice 菜单删除部分候选，但证据、问题与保留候选文本均不改变；
- 删除动作不会让任务目标、默认选项、比较基准或“以上皆是”等候选失效；
- 不含已知的吸引、折衷、诱饵或容量效应；
- 原菜单中被保留候选的总概率大于零；
- 至少保留两个候选。

真实人类决策可能合理地违反 IIA，因此论文中应把 CHO 表述为“模型在受控菜单缩减下的稳定性”，不能泛化为普遍理性定律。

### 7.2 变换

由原菜单 `C` 选取子菜单 `S⊂C`，保持保留候选的显示顺序，另做顺序随机化时要单独标 REP。建议对子菜单大小与被删除候选概率质量分层抽样。

### 7.3 条件误差

条件一致性要求：

\[
q_i^*=\frac{p_i}{\sum_{j\in S}p_j},\ i\in S,
\qquad E_{CHO-cond}=d_{TV}(q^*,q^{model}).
\]

```python
submenu_conditional_consistency_error(full_distribution, submenu_indices, submenu_distribution)
```

### 7.4 赔率误差

对所有保留候选对 `(i,j)`，条件化应保持赔率。诊断指标为平均绝对 log-odds 变化：

\[
E_{CHO-odds}=\operatorname{mean}_{i<j}
\left|\log\frac{p_i}{p_j}-\log\frac{q_i}{q_j}\right|.
\]

该指标要求相关概率严格大于零；含零概率时报告 undefined/invalid，不添加任意 epsilon。实现接口：

```python
submenu_odds_consistency_error(full_distribution, submenu_indices, submenu_distribution)
```

## 8. 构造、抽样与统计报告规范

1. **先验登记关系。** 在查看模型输出前锁定 relation type、变换参数、排除规则与主指标，避免按结果挑选“容易一致”的样本。
2. **分层抽样。** 每类关系至少按 `source × task_type × modality_requirement × difficulty` 分层；小层全取，大层用固定种子等概率抽样。报告总体宏平均，也报告各层结果和样本数。
3. **人工审校。** REP/BAT 可规则验证；MEA/LOG/CHO 的语义关系至少双人独立标注，分歧仲裁，并报告一致率。自动生成后必须抽检，不能把 LLM 自审当作人工 gold。
4. **避免伪重复。** 同一 canonical 样本的所有变体计为一个 relation group。置信区间以 group 为重采样单位，不能把每个变体当独立样本。
5. **控制随机性。** 保存模型版本、温度、seed、prompt hash、媒体 hash、batch size、候选映射及原始概率。若 API 不保证确定性，每个条件重复运行并区分 run-to-run noise 与 transformation effect。
6. **多重比较。** 五类关系各指定一个主指标；额外切片为诊断性分析。若对模型差异做大量显著性检验，应控制 FDR 或提供同时置信区间。
7. **失败可见。** 分布解析失败、概率和错误、零概率导致 odds 未定义等都单独计入 invalid 率；不得从分母中无声删除。

## 9. 最小结果表

论文主表至少包含以下列：

| Model | Valid % | REP TV ↓ | BAT TV ↓ | MEA-neg TV ↓ | MEA-merge TV ↓ | LOG gap ↓ | LOG viol. % ↓ | CHO-cond TV ↓ | CHO-odds ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

所有 `↓` 指标越低越好，理想值为 `0`。应在表注中写明样本数、置信区间方法、温度/重复次数，以及 CHO 的 IIA 前提。不要把不同量纲的 TV、概率 gap 与 log-odds 直接平均成一个缺乏解释的总分；如确需排名，应先在论文中预注册标准化与权重。

## 10. 可复现实现

标准库实现位于 `mmjevbench/coherence.py`。函数均验证概率边界、归一化、索引映射和关系结构。手算单元测试位于 `tests/test_coherence.py`，覆盖精确一致、已知非零误差与关键 invalid 输入。运行：

```bash
python -m pytest tests/test_coherence.py
```
