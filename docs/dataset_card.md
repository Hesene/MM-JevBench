# MM-JevBench-10k Dataset Card

版本：`MM-JevBench-10k-v1.0`  
日期：2026-10-12

## Intended use

MM-JevBench-10k 用于研究多模态候选式决策模型的准确性、概率校准、选择性预测、模态依赖、Jev 一致性和推理效率。适合离线研究评测，不适合直接作为医疗、金融、司法、执法或无人监督内容处置系统的上线依据。

当前版本不包含安全内容评测轨道，因此不能用于证明模型“安全”或“不安全”。

## Composition

| Track | Source | Canonical | Dev | Test | Groups |
|---|---|---:|---:|---:|---:|
| Academic reasoning | CMMMU | 760 | 152 | 608 | 752 |
| Chinese exam reasoning | MULTI | 4,994 | 999 | 3,995 | 4,994 |
| GUI action type | OmniGUI | 2,572 | 514 | 2,058 | 708 |
| General multimodal reasoning | MMBench-Dev-CN | 1,164 | 233 | 931 | 1,121 |
| Chinese culture reasoning | CCBench | 510 | 102 | 408 | 504 |
| **Total** | — | **10,000** | **2,000** | **8,000** | **8,079** |

旧三轨 1,500 条 anchor 的 ID 与 split 100% 保留。另有 61,508 条 coherence 变体和 54,508 个关系定义；它们依赖 canonical parent，不计入 10,000 条总量。

## Data format

每条记录包含：

- 稳定 ID、schema version、track、domain、language；
- 多模态 state：context、question、media、history；
- 互斥候选及稳定 key/value；
- source 或 derived gold；
- `group_id` 与 dev/test split；
- 来源版本、source ID、抽样元数据与审查状态。

`gold.outcome_distribution` 对确定性答案采用 one-hot。它支持 proper scoring 和 calibration evaluation，但不代表人类信念分布或真实事件频率。若未来加入人群判断，必须另存真实投票人数和 vote distribution。

## Collection and sampling

抽样、eligibility、anchor 嵌套、group split 和统计推断见 `sampling_protocol_10k.md`。

核心原则：

- 模型实验前冻结抽样；
- 共享媒体、parent problem 与 episode 不跨 split；
- dev 仅用于 prompt、解析、阈值和校准；
- test 不参与适配；
- 主榜按五轨等权，不把样本量最大的 MULTI 当作默认现实分布；
- 推断以 group 而不是 record 为独立单位。

## Known limitations

- 五个来源均为公开 benchmark 或公开考试材料，存在训练污染风险；
- 当前尚未完成 10,000 条全量人工审查与模态必要性双人标注；
- MMBench-Dev-CN 与 CCBench 是公开 dev/culture benchmark，高分不等于对未见分布的泛化；
- CMMMU 的有标签池有限，并混合单选和二元判断；
- MULTI 有意做分层覆盖，样本比例不等于原始来源比例；
- OmniGUI 主任务是从开放式动作派生的 closed-world action type，不能替代坐标、文本参数和官方开放动作指标；
- OmniGUI 2,572 个 step 聚类在 708 个 episode，不能按 2,572 个独立样本计算 CI；
- CCBench 的文化标签可能受地域、时代和来源标注口径影响；
- coherence 变体是关系测量，不是额外独立题；
- 当前没有新采集 sealed test，无法排除模型记忆公开题目。

## Bias and representativeness

数据主要是中文教育、通用图文、文化知识和桌面/移动 GUI 场景，不代表所有语言、地区、残障辅助场景或真实决策成本。五轨等权是 benchmark 设计选择，不是现实任务先验。任何部署外推都应重新定义目标总体并收集相应数据。

## Privacy, ethics and safety

OmniGUI 截图、音频或视频可能包含账号名、通知或其他界面信息；公开前必须执行隐私复核和必要的脱敏。考试题与网络图片可能受第三方版权约束。不要从本 release 的存在推断可以自由重新分发全部原媒体。

不得将 benchmark 用于自动化高风险个体决策，也不得把文化或学科题目的单一 gold 用作评价个人能力、身份或群体价值的依据。

## Licensing and redistribution

代码许可与来源数据许可分离。每条记录保留 component provenance；OmniGUI 受 CC BY-NC-SA 4.0 条件约束，其他来源的题目与媒体可能另有权利人。稳妥发布方式是优先发布 schema、source ID、manifest、哈希和重建脚本，并在重新打包媒体前完成机构级许可审查。

## Validation status

已完成：数量、schema、ID、候选/gold 维度、group split、anchor 嵌套和 coherence 关联的机器校验。

尚未完成：全量人工语义审查、五来源近重复复核、论文级模型实验、sealed test 和最终媒体/许可审计。详见 `build_report_10k.md` 与项目根目录 `BLOCKERS.md`。

## Maintenance

发现错误时不得静默覆盖。应保留 source label、增加 adjudication 证据、更新 exclusion/manifest、提升版本号并重新运行全部审计。已经用于论文结果的 release 必须保持可复现。
