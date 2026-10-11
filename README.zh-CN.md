<div align="center">

# MM-JevBench

### 面向校准、多模态候选决策与 Jev 一致性的评测基准

[![Release](https://img.shields.io/badge/release-v1.0-2563eb)](https://github.com/Hesene/MM-JevBench)
[![Samples](https://img.shields.io/badge/canonical-10%2C000-0f766e)](#数据规模)
[![Test](https://img.shields.io/badge/test-8%2C000-7c3aed)](#test-准确率)
[![Task](https://img.shields.io/badge/task-multimodal%20decision-e11d48)](#题型设计)

**[English](README.md)** · **简体中文**

</div>

MM-JevBench 是一个多模态候选式决策评测集。模型读取图像、文本、音频、视频或 GUI 历史状态，并为给定候选项输出完整概率分布。

当前发布版本为 `MM-JevBench-10k-v1.0`。

> **核心规模：** 5 个数据来源 · 10,000 条 canonical 样本 · 2,000 条 dev · 8,000 条 test · 8,079 个防泄漏 group

## 导航

[数据规模](#数据规模) · [题型设计](#题型设计) · [选项构造](#选项设计与构造) · [模型结果](#已评测模型) · [案例](#代表性-cases) · [生成逻辑](#生成逻辑) · [数据文件](#数据文件) · [快速验证](#快速验证)

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

## 已评测模型

| 模型 | 参数规模 | 多模态决策方式 | 官方权重 |
|---|---:|---|---|
| [Clef](https://huggingface.co/Cloudflare/clef) | 27B | 图像/视频输入，typed questions，直接输出候选概率 | [Cloudflare/clef](https://huggingface.co/Cloudflare/clef/tree/main)（BF16 Safetensors，Apache-2.0） |
| [JEV-27B-VL](https://huggingface.co/autotrust/JEV-27B-VL) | 27B | 文本与图像的 Jev-style choice 决策，输出完整候选概率 | [autotrust/JEV-27B-VL](https://huggingface.co/autotrust/JEV-27B-VL/tree/main)（BF16 分片权重及 decision adapter/head，Apache-2.0） |
| [Clef-Flash](https://huggingface.co/Cloudflare/clef-flash) | 9B | 图像/视频输入，Jev/SystemOne-compatible typed decision | [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash/tree/main)（BF16 Safetensors，Apache-2.0） |

### Test 准确率

以下结果为 zero-shot 多模态候选决策准确率；同一题目的候选集合和输入模板在三个模型间保持一致。

#### 总体榜单

| 模型 | 各数据集平均准确率<br><sub>每个数据集占 20%</sub> | 8,000 条样本加权平均 |
|:---|---:|---:|
| **JEV-27B-VL** | 🥇 **74.24%** | 70.10% |
| **Clef** | 74.22% | 🥇 **70.90%** |
| **Clef-Flash** | 69.90% | 64.83% |

#### 分数据集结果

| 数据集 | Test 样本 | Clef | JEV-27B-VL | Clef-Flash |
|:---|---:|---:|---:|---:|
| CMMMU | 608 | 63.9% | 🥇 **65.8%** | 62.8% |
| CCBench | 408 | 81.4% | 🥇 **82.6%** | 81.4% |
| MULTI | 3,995 | 🥇 **69.2%** | 68.7% | 65.9% |
| MMBench-Dev-CN | 931 | 91.9% | 🥇 **92.7%** | 91.3% |
| GUI action decision | 2,058 | 🥇 **64.7%** | 61.4% | 48.1% |

各数据集平均准确率是将五个数据集的准确率直接取平均，每个数据集各占 20%，用于避免样本量较大的 MULTI 和 GUI 数据集主导总体结论；样本加权平均则按各数据集的 test 样本数计算。由于输入的逐项准确率保留到小数点后一位，加权平均为据此计算的近似值。

### 代表性 Cases

下面列出三个来自 test split 的真实样本。为便于阅读，三个预览图单独存放在 `docs/assets/readme/`；Parquet 仍只保存完整媒体包的相对路径，不内嵌媒体二进制。

#### Case 1：通用视觉空间关系

<table>
  <tr>
    <td width="46%" align="center"><img src="docs/assets/readme/case-mmbench-zebra.jpg" width="430" alt="MMBench-Dev-CN case：斑马位于画面右侧"><br><sub>MMBench-Dev-CN · spatial relation</sub></td>
    <td width="54%"><strong>问题</strong><br>斑马在哪里？<br><br><strong>候选项</strong><br>A · 它在右边<br>B · 它在左边<br>C · 它在顶部<br>D · 它在底部<br><br><strong>Gold　A · 它在右边</strong></td>
  </tr>
</table>

<details><summary>样本信息与媒体路径</summary><br><strong>ID：</strong><code>mmjev_mmbench_dev_cn_1000</code><br><strong>来源：</strong>MMBench-Dev-CN<br><strong>图像：</strong><code>datasets/media/mmbench_dev_cn/a0/a03f851109b2cfafd34a05a5cb687dafbae5435f6f7a59df2a66f1eb30a012c8.jpg</code></details>

#### Case 2：中文考试图文推理

<table>
  <tr>
    <td width="46%" align="center"><img src="docs/assets/readme/case-multi-geography.png" width="360" alt="MULTI 高中地理 case：大陆面积与平均海拔散点图"><br><sub>MULTI · 高中地理</sub></td>
    <td width="54%"><strong>问题</strong><br>Y 大陆是 <code>[MASK]</code><br><br><strong>候选项</strong><br>A · 亚欧大陆<br>B · 澳大利亚大陆<br>C · 北美大陆<br>D · 南美大陆<br><br><strong>Gold　B · 澳大利亚大陆</strong></td>
  </tr>
</table>

<details><summary>样本信息与媒体路径</summary><br><strong>ID：</strong><code>mmjev_multi_gzdl_3_1</code><br><strong>来源：</strong>MULTI（高中地理）<br><strong>图像：</strong><code>datasets/media/multi/gzdl/3_1.png</code></details>

#### Case 3：GUI 下一步动作决策

<table>
  <tr>
    <td width="38%" align="center"><img src="docs/assets/readme/case-omnigui-tasty.png" width="230" alt="OmniGUI Tasty case：食谱详情页面"><br><sub>OmniGUI · Tasty · T0505 / step 0</sub></td>
    <td width="62%"><strong>任务</strong><br>收藏该食谱。<br><br><strong>问题</strong><br>根据当前多模态状态和历史动作，下一步应选择哪一种动作类型？<br><br><strong>候选空间</strong><br>13 种固定动作：<code>WAIT</code>、<code>TAP</code>、<code>DOUBLE_TAP</code>、<code>LONG_PRESS</code>、四向滑动、<code>INPUT</code>、<code>BACK</code>、<code>HOME</code>、<code>TASK_COMPLETE</code>、<code>TASK_IMPOSSIBLE</code><br><br><strong>Gold　B · TAP</strong></td>
  </tr>
</table>

<details><summary>样本信息与媒体路径</summary><br><strong>ID：</strong><code>mmjev_omnigui_3dae6b3d0adbb2d668dd</code><br><strong>来源：</strong>OmniGUI（Tasty，episode <code>T0505</code>，step 0）<br><strong>多模态输入：</strong>同一步骤的界面截图、音频和视频<br><strong>截图：</strong><code>datasets/media/omnigui/tasty/media/T0505/1.png</code></details>

当前仅发布聚合准确率，尚未获得三个模型逐样本的预测概率，因此这里不展示或推测单个 case 的模型输出。后续公开 prediction JSONL 后，可在相同 case 下补充三个模型的完整候选概率分布。

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

## 引用

如果 MM-JevBench 对你的研究有帮助，请引用本仓库：

```bibtex
@misc{mmjevbench2026,
  title        = {MM-JevBench: Benchmarking Calibrated Multimodal Choice Decisions and Jev Coherence},
  author       = {Hesene},
  year         = {2026},
  howpublished = {\url{https://github.com/Hesene/MM-JevBench}},
  note         = {Version 1.0}
}
```

仓库地址：<https://github.com/Hesene/MM-JevBench>

---

<div align="center">

**[返回顶部](#mm-jevbench)** · **[English](README.md)**

</div>
