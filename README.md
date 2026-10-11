# MM-JevBench

MM-JevBench 是一个多模态候选式决策评测集。模型读取图像、文本、音频、视频或 GUI 历史状态，并为给定候选项输出完整概率分布。

当前发布版本为 `MM-JevBench-10k-v1.0`。

## 数据规模

| Track | 来源 | Canonical | Dev | Test | Groups |
|---|---|---:|---:|---:|---:|
| Academic reasoning | CMMMU | 760 | 152 | 608 | 752 |
| Chinese exam reasoning | MULTI v1.3.1 | 4,994 | 999 | 3,995 | 4,994 |
| GUI action decision | OmniGUI | 2,572 | 514 | 2,058 | 708 |
| General multimodal reasoning | MMBench-Dev-CN | 1,164 | 233 | 931 | 1,121 |
| Chinese culture reasoning | CCBench | 510 | 102 | 408 | 504 |
| **Total** | **5 sources** | **10,000** | **2,000** | **8,000** | **8,079** |

所有 canonical 样本均为闭集选择决策。普通视觉题包含 2–7 个候选项，OmniGUI 包含 13 个固定动作类型。Gold 使用来源提供的唯一正确答案，并表示为 one-hot `outcome_distribution`；模型输出为总和等于 1 的候选概率分布。

## 题型设计

| 题型 | 来源 | 数量 | 候选数 | 决策依据 |
|---|---|---:|---:|---|
| 学科视觉单选 | CMMMU | 655 | 4 | 图片、题干与学科知识 |
| 学科视觉判断 | CMMMU | 105 | 2 | 图片、题干与学科知识 |
| 中文考试选择 | MULTI | 4,994 | 2–7 | 图片、题干与考试知识 |
| 通用视觉选择 | MMBench-Dev-CN | 1,164 | 2–4 | 图片与文本问题 |
| 中华文化选择 | CCBench | 510 | 4 | 图片、文本与文化知识 |
| GUI 下一步动作 | OmniGUI | 2,572 | 13 | 当前界面、多媒体上下文与操作历史 |

整个数据集按候选数统计为：2 项 783 题、3 项 108 题、4 项 6,534 题、5 项 2 题、7 项 1 题、13 项 2,572 题。所有题型统一为 `task_type: "choice"`，但保留 `domain`、`source.dataset` 和来源元数据，便于按能力与来源分别报告结果。

## 选项设计与构造

- **来源原生选项**：CMMMU、MULTI、MMBench-Dev-CN 和 CCBench 保留上游题目的候选内容，不生成合成干扰项；仅规范化选项标记、空白和大小写。
- **判断题规范化**：CMMMU 判断题统一为“错误（错）”与“正确（对）”两个候选，并将来源答案映射到对应索引。
- **GUI 动作闭集化**：OmniGUI 将下一步操作映射为 13 类固定候选：`WAIT`、`TAP`、`DOUBLE_TAP`、`LONG_PRESS`、`SWIPE_UP`、`SWIPE_DOWN`、`SWIPE_LEFT`、`SWIPE_RIGHT`、`INPUT`、`BACK`、`HOME`、`TASK_COMPLETE`、`TASK_IMPOSSIBLE`。坐标、输入文本等参数保留在元数据中，不作为新的候选项。
- **统一候选结构**：每个候选保存 `key`、`text` 和可选 `value`。普通题通常以 A/B/C 等作为 `key`；GUI 题的 `value` 保留来源动作编码。
- **固定 canonical 顺序**：正式数据保留来源选项顺序。coherence 测试中的 `REP` 关系会确定性重排候选并同步重映射 gold，但这些变体不计入 10,000 条 canonical 样本。
- **Gold 与模型分数**：`label_index` 和 `label_key` 指向唯一正确项，`outcome_distribution` 为来源 gold 对应的 one-hot 分布。被评测模型须为每个候选输出 `[0,1]` 内的概率，且总和为 1；当前版本不把 one-hot gold 解释为人类主观不确定性。

单条候选与预测的最小形式如下：

```json
{
  "candidates": [
    {"key": "A", "text": "候选 A", "value": null},
    {"key": "B", "text": "候选 B", "value": null}
  ],
  "label_index": 1,
  "label_key": "B",
  "outcome_distribution": [0.0, 1.0],
  "prediction": {"probabilities": [0.15, 0.85]}
}
```

## 待评测模型

| 模型 | 覆盖模态 | 计划设置 | 状态 |
|---|---|---|---|
| [OpenJev Multimodal](https://github.com/jev-skills/openjev-multimodal)（`quality` profile） | 文本、图像；视频抽帧 | Jev-compatible `Choice` 接口；zero-shot；只在 dev 冻结输入模板，随后一次性评测 test | 待评测 |

OpenJev Multimodal 是面向 typed decision 的多模态 Jev-compatible 模型：每个问题只读取一个候选 token，并返回全部选项的条件概率，因此它属于本基准要评测的目标模型类型，而不是普通生成式 VLM。首轮实验固定使用 `quality` profile，并记录实际权重、量化版本、推理后端和 commit。当前实现不原生支持音频，视频仅支持抽帧输入，因此主表应同时报告全体可评样本与纯图文子集，不能把缺失模态填充后的结果表述为原生全模态能力。为避免测试集调参，输入模板和概率读取规则应在 dev 阶段冻结；GUI 轨道除 13 类动作决策外，应另行报告包含坐标与文本参数的上游 open-action 指标。

## 生成逻辑

1. **冻结来源版本**：记录每个来源的 revision、原始文件大小和 SHA-256。
2. **统一 schema**：将题干、媒体、候选、gold、来源、抽样信息与 `group_id` 转换为统一 JSONL。
3. **资格过滤**：只保留具有公开 gold、合法候选和有效媒体引用的样本；MMBench/CCBench 排除 CircularEval 旋转副本。
4. **确定性抽样**：
   - CMMMU 纳入有效单选题和判断题；
   - MULTI 按 `subject × image_bin × Elite` 分层，从唯一 problem group 中抽取；
   - OmniGUI 纳入全部合法 action steps；
   - MMBench-Dev-CN 和 CCBench 使用去除旋转副本后的 canonical 集合。
5. **分组切分**：以共享媒体、problem 或 GUI episode 为 group；同一 group 不得跨 dev/test。最终为 2,000 dev、8,000 test，跨 split group leakage 为 0。
6. **嵌套扩展**：旧版 1,500 条 anchor 的 ID 与 split 全部保留，新增样本只从剩余抽样框确定性补入。
7. **跨源去重**：联合使用规范化文本、图像 SHA-256 与感知哈希筛查；当前未发现必须删除的跨来源精确重复。

详细抽样方法见 [`docs/sampling_protocol_10k.md`](docs/sampling_protocol_10k.md)，来源版本见 [`docs/data_sources.md`](docs/data_sources.md)。

## 数据文件

| 文件 | 内容 |
|---|---|
| `datasets/processed/10k/mmjevbench_10k.jsonl` | 完整 10,000 条 canonical 数据 |
| `datasets/parquet/dev.parquet` | 2,000 条 dev，适合直接加载与预览 |
| `datasets/parquet/test.parquet` | 8,000 条 test，适合直接加载与预览 |
| `datasets/coherence/10k/relations.jsonl` | 54,508 条 Jev coherence 关系 |
| `datasets/manifests/10k/release_media.jsonl` | 15,718 个媒体引用及 SHA-256 |
| `schemas/mmjevbench.schema.json` | 统一数据 schema |

来源媒体总量约 6.1 GB，不直接提交 GitHub。媒体路径、哈希和重建信息保存在 manifest 与转换脚本中。超过 GitHub 单文件限制的 coherence variants 可由 canonical 数据确定性重建。

## 快速验证

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python scripts\validate_dataset.py datasets\processed\10k\mmjevbench_10k.jsonl
.\.venv\Scripts\python -m pytest
```

## 数据来源与许可

数据来自 CMMMU、MULTI-Benchmark、OmniGUI、MMBench-Dev-CN 和 CCBench。代码与统一标注不会改变上游题目及媒体的原始许可；使用或再分发前请查阅 [`docs/data_sources.md`](docs/data_sources.md)。
