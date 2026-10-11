# 当前阻塞项与发布 Gate

10,000 条五轨 canonical、全部引用媒体和 coherence suite 已生成。当前没有外部数据授权阻塞项；剩余工作集中在人工质量验证、模型实验和论文外部有效性。

## 1. 全量人工审查

尚未完成以下论文级人工工作：

- 10,000 条媒体—题目—候选—gold 一致性快速审查；
- modality dependency 双人独立标注；
- 分歧的第三人裁决；
- 解析异常、低质量媒体、共享媒体和文化争议项的重点复核；
- reviewer、时间、agreement 与 adjudication trail 的结构化记录。

机器校验和模型自评不能替代人工审查。未经完成，不应声称数据“已全量人工验证”。

## 2. 去重候选的人工裁决

五来源自动审计已经完成：10,689/10,689 张引用图像可读，未发现跨来源精确题文重复、精确图像重复或必须删除的精确泄漏。报告位于 `reports/cross_source_dedup_10k.md`。

自动方法仍召回 166 个近似文本候选。它们需要人工查看题干、候选、gold 与媒体后裁决；自动相似度不能直接作为删除依据。公开 benchmark 进入模型训练语料的污染风险也仍需在论文中说明。

## 3. 论文级模型实验

10k uniform/dev-prior 已覆盖全部 8,000 条 test，用于验证概率格式和评测链路。主榜仍需运行：

- text-only 与 OCR/caption baselines；
- 多个开源 VLM 家族；
- 至少一个原生音频/视频模型；
- GUI-agent 专用模型；
- Jev/decision-model adapter；
- 有预算时的强闭源参考模型。

所有 prompt、parser、temperature 和拒答阈值只能在 dev 上确定。需要记录模型精确版本、概率来源、invalid rate、硬件、延迟、吞吐和成本。

## 4. Sealed/new test

五个来源均为公开 benchmark 或公开材料，可能进入模型训练语料。正式 benchmark paper 最好新增 20%–30% 新采集或 sealed test，并进行独立标注。不能通过表面改写公开题伪造“未见测试集”。

如果本版本直接投稿，必须把训练污染作为主要限制，并避免将高分解释为真实部署泛化。

## 5. 许可、隐私与再分发

发布前仍需确认：

- 各来源题目和媒体的再分发边界；
- OmniGUI 的 CC BY-NC-SA 4.0 归因与限制；
- GUI 截图、音频、视频中的账号、通知和个人信息；
- 网络图片、考试材料和文化内容的第三方权利；
- 在权利不清晰时只发布 manifest、hash 和重建脚本。

## 6. 完成标准

只有同时满足以下条件，才可将版本标记为“论文实验完成”：

1. 人工审查和 agreement 报告已归档；
2. 五来源去重候选全部裁决；
3. 模型矩阵在冻结 test 上一次性运行；
4. group-aware paired CI 与 coherence 结果已生成；
5. 污染、伦理、许可和隐私限制进入论文与数据卡；
6. 所有 release、prediction、manifest 和 report 均有版本与 SHA-256。
