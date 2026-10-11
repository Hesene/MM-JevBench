# MM-JevBench-10k 构建报告

冻结日期：2026-10-12  
版本：`MM-JevBench-10k-v1.0`  
实际存储位置：`E:\Codex\MM-JevBench`

## 1. 构建结论

五轨 canonical release 已生成并通过 schema 与 release-level 校验：

| Track | Canonical | Dev | Test | Groups |
|---|---:|---:|---:|---:|
| CMMMU | 760 | 152 | 608 | 752 |
| MULTI | 4,994 | 999 | 3,995 | 4,994 |
| OmniGUI | 2,572 | 514 | 2,058 | 708 |
| MMBench-Dev-CN | 1,164 | 233 | 931 | 1,121 |
| CCBench | 510 | 102 | 408 | 504 |
| **合计** | **10,000** | **2,000** | **8,000** | **8,079** |

主文件：`datasets/processed/10k/mmjevbench_10k.jsonl`

- 文件大小：19,402,600 bytes；
- SHA-256：`d0dbcafaab30baec4deed99fefa72f033fdc1a7fde934aeea2fdd15a8a7b4ce1`；
- schema issues：0；
- release issues：0；
- 1,500/1,500 个旧 anchor ID 与 split 保持不变。

验证摘要位于 `reports/release_10k_summary.json`。

## 2. Split 与 group 审计

| Track | Dev records | Dev groups | Test records | Test groups |
|---|---:|---:|---:|---:|
| CMMMU | 152 | 152 | 608 | 600 |
| MULTI | 999 | 999 | 3,995 | 3,995 |
| OmniGUI | 514 | 134 | 2,058 | 574 |
| MMBench-Dev-CN | 233 | 226 | 931 | 895 |
| CCBench | 102 | 100 | 408 | 404 |
| **合计** | **2,000** | **1,611** | **8,000** | **6,468** |

检查结果：

- 没有 `group_id` 跨 dev/test；
- 同一 OmniGUI episode 的所有 step 位于同一 split；
- CMMMU、MMBench 与 CCBench 的共享媒体题按 group 绑定；
- MULTI 当前入选项来自 4,994 个唯一 problem group；
- 所有 coherence 变体继承 canonical parent 的 test split。

记录级数量不能作为独立样本量。正式 CI 必须按 group 分层 bootstrap，OmniGUI 必须按 episode 聚类。

## 3. Anchor 保留

扩展以旧三轨 1,500 条 release 为 anchor。合并脚本逐 ID 验证：

- 1,500 个 anchor 全部进入 10k；
- 1,500 个 split 全部原样保留；
- anchor 不因新来源、配额或后验模型表现被替换。

这保证早期 smoke test 与 10k 后续实验可以在同一题集子集上直接比较。

## 4. 三轨兼容子集

`datasets/processed/10k/mmjevbench_10k_public8000.jsonl` 包含 CMMMU 760、MULTI 4,668、OmniGUI 2,572，共 8,000 条；dev 1,600、test 6,400，6,128 个 group。

- 文件大小：16,096,551 bytes；
- SHA-256：`14e688c0c3431dfe768bd9e7611760faa78b7505c9be16129cbf80c1ae6092ac`。

它是兼容性产物，不是五轨 10k 主榜。主实验应使用 10k 文件并按五轨等权报告。

## 5. Coherence suite

在 8,000 条 held-out test canonical cases 上确定性生成：

| Family | Relations |
|---|---:|
| REP | 22,754 |
| BAT | 1,000 |
| MEA | 15,377 |
| LOG | 8,000 |
| CHO | 7,377 |
| **合计** | **54,508** |

产物：

- `datasets/coherence/10k/variants.jsonl`：61,508 条，SHA-256 `5122ccf1c7590cf38ddd4f8cfcfcaddd7a7aab2df1e5b09f105fbb08da22fcd7`；
- `datasets/coherence/10k/relations.jsonl`：54,508 条，SHA-256 `7817533ec1dfa9ba1666c588bc9a53fb832fa1274daf9bc3ca248caa0719742f`。

所有关系位于 test；变体不是额外独立 canonical 样本。详细公式和适用条件见 `coherence_protocol.md`。

## 6. 媒体状态

最终媒体物化和存在性审计已完成：

- OmniGUI 请求 7,650 个媒体文件，失败 0，合计 5,693,823,822 bytes；
- 10k release 引用 15,718 个唯一媒体路径；
- 本地存在 15,718/15,718，缺失 0；
- release 引用媒体合计 6,104,037,654 bytes；
- media manifest SHA-256：`e73fc906bb01aed0e968f3cd4bdd5d3c3193abdd4b815fa9b42ca5f52dc935e5`；
- group leakage：0。

发布包仍应保留媒体 manifest，并在移动、压缩或重新下载后复验路径、字节数和 SHA-256。

## 7. 已完成的机器校验

- canonical 数量、逐轨配额与 2,000/8,000 split；
- JSON Schema、ID 唯一性、候选维度和 gold 索引；
- `group_id` split 不变量；
- anchor ID 与 split 嵌套；
- CircularEval 旋转副本过滤；
- coherence 数量与 parent/group 关联；
- release 文件与 coherence 文件 SHA-256 冻结。

机器校验只能证明格式和声明的不变量成立，不能证明题目语义、gold、媒体相关性或文化判断一定正确。

## 8. 尚未完成

以下事项不能在论文中冒充已经完成：

1. 10,000 条全量人工题目—媒体—候选—gold 审查；
2. modality dependency 双人独立标注与第三人裁决；
3. 五来源全量跨源近重复人工复核；
4. 10k 上的论文级模型矩阵、温度校准与效率测量；
5. 新采集或 sealed test，用于缓解公开 benchmark 训练污染；
6. 数据许可、隐私、截图账号信息和媒体再分发边界复核。

旧版 uniform 与 dev-prior 结果只验证了三轨 anchor 管线，不能作为 10k 五轨论文 baseline。

## 9. 可主张与不可主张

当前可以主张：

- 已构建一个 10,000 条、五轨、group-aware、anchor-preserving 的候选式多模态决策 release；
- 已生成 61,508 条变体和 54,508 个 Jev 关系定义；
- 已实现并通过机器校验的统一 schema、合并、split、媒体与一致性管线。

当前不能主张：

- 数据已完成全量人工验证；
- 已证明某模型优于其他模型；
- benchmark 不受训练污染；
- 10,000 条记录彼此统计独立；
- 当前版本覆盖模型安全能力或真实世界全部 agent 能力。
