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
