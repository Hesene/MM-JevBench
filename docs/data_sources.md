# MM-JevBench-10k 数据来源审计

审计日期：2026-10-12。实现以记录中的 `source.version`、`configs/sources.yaml` 和冻结输入 artifact 为准。

## CMMMU

- 论文：[CMMMU: A Benchmark for Chinese Multi-modal Multi-type Question Understanding and Reasoning](https://arxiv.org/abs/2401.11944)
- 仓库：[CMMMU-Benchmark/CMMMU](https://github.com/CMMMU-Benchmark/CMMMU)
- 数据：[m-a-p/CMMMU](https://huggingface.co/datasets/m-a-p/CMMMU)
- 固定 revision：`d7ba0c8d5b73a45a0897ec29a9e841fab8acdde2`
- 仓库许可：Apache-2.0；具体题目和媒体仍需保留来源 provenance。

官方总量为 12,012 题，dev/val/test 为 112/900/11,000；test 不公开答案。可离线使用的有标签池为 dev + val 共 1,012 条，实测为单选 662、判断 105、填空 245，全部带图。

当前轨道纳入：

- 658 条可解析单答案选择题中，先排除 3 条冻结的跨源重复/高风险近重复，保留 655 条；
- 全部 105 条判断题，映射为“错误（错）/正确（对）”二选一；
- 共享媒体样本保留，但写入相同 group。

最终为 760 records、752 groups。填空和多答案题不进入当前 one-hot Choice 主榜。

## MULTI-Benchmark

- 论文：[MULTI: A Multi-modal Understanding Leaderboard with Text, Images, Audio, and Video](https://arxiv.org/abs/2402.03173)
- 仓库：[OpenDFM/MULTI-Benchmark](https://github.com/OpenDFM/MULTI-Benchmark)
- 数据：[OpenDFM/MULTI-Benchmark](https://huggingface.co/datasets/OpenDFM/MULTI-Benchmark)
- 固定数据包：`MULTI_v1.3.1_20251016_release.zip`
- 固定 revision：`45286aa9c0ed9cac80d0435d6a371f58c460cf83`
- 输入 ZIP：504,311,784 bytes。

实际 census 为 17,250 problem groups、18,429 question items；题型包括单选、多选、填空、解答和其他。2025-10-16 发布包提供全量答案。

当前 converter 仅纳入至少一张图、有合法 gold、候选可严格解析的单选题。严格 frame 为 5,784 items、5,583 problem groups；10k 版本按 `subject × image_bin × Elite` 分层选取 4,994 个唯一 problem group。

仓库代码为 MIT，但数据卡没有把所有考试题和网络媒体统一授予独立宽松许可。建议发布 source ID、manifest、哈希和重建脚本，不默认重新打包全部原题与媒体。

## OmniGUI

- 论文：[OmniGUI: Towards General-Purpose GUI Agents](https://arxiv.org/abs/2605.18758)
- 仓库：[omni-gui/OmniGUI](https://github.com/omni-gui/OmniGUI)
- 数据：[OmniGUI/OmniGUI](https://huggingface.co/datasets/OmniGUI/OmniGUI)
- 固定 revision：`2c9031077541186f6fb1f2514cb62446c811ffd4`
- 许可：CC BY-NC-SA 4.0。

当前固定 HF release 实测为 708 episodes、2,572 steps；本项目以下载 census 为准。主索引含 task instruction、action history、图像/音频/视频路径、target action、app 和 cognitive dimension。

10k 版本纳入全部 2,572 个合法步骤，并以 episode 作为 `group_id`。主任务是 13 类 action-type Choice；原始 action+parameters 保留用于开放动作评测。派生 action-type 不能替代官方坐标、文本参数或任务成功指标。

## MMBench-Dev-CN

- 论文：[MMBench: Is Your Multi-modal Model an All-around Player?](https://arxiv.org/abs/2307.06281)
- 仓库：[open-compass/MMBench](https://github.com/open-compass/MMBench)
- 数据：[open-compass/MMBench](https://huggingface.co/datasets/open-compass/MMBench)
- 固定 revision：`8eaac9ae42e22eaf42863b218455acd51268ba1c`
- 冻结输入：`MMBench_DEV_CN.tsv`。

CircularEval 会为同一语义题生成候选旋转版本。当前 converter 只保留 `index < 1,000,000` 的 canonical pass，并要求问题、至少两个候选、合法答案和可解码 JPEG 均有效。

最终有效 frame 为 1,164 records、1,121 image-hash groups，全部进入 10k。类别覆盖图像场景、属性/动作识别、物理和空间关系、OCR、结构化图文理解等。

## CCBench

- 项目与数据入口同 MMBench；
- 固定 revision：`open-compass/MMBench@8eaac9ae42e22eaf42863b218455acd51268ba1c`；
- 冻结输入：`CCBench.tsv`。

CCBench 评测中国文化相关图文知识。当前 converter 同样排除 CircularEval 旋转版本，并严格校验问题、候选、gold 与 JPEG。最终有效 frame 为 510 records、504 image-hash groups，全部进入 10k。

七个主要 category 为 food/clothes、cultural relic、scenery/building、traditional show、calligraphy/painting、sketch reasoning 和 historical figure。文化标签可能随地域、时代和来源口径变化，人工审查应记录争议而不是把 source gold 当作普遍真理。

## 组合许可与发布边界

统一 JSON schema 不会统一底层权利。项目代码可以采用软件许可，但每条数据仍继承来源与媒体权利：

- OmniGUI 明确受 CC BY-NC-SA 4.0 约束；
- CMMMU、MULTI、MMBench 与 CCBench 的题目、考试材料和网络图片可能涉及第三方权利；
- provenance、source ID、revision 和必要 attribution 必须保留；
- 发布前应由项目负责人或机构法务确认原题、截图、音频、视频和网络图片的再分发边界；
- 在权利不清晰时，优先发布 manifest 与重建脚本，而不是复制全部媒体。

## 来源风险汇总

| 来源 | 主要风险 | 缓解措施 |
|---|---|---|
| CMMMU | test 无 gold；有标签池小；与考试题跨源重复 | 只用 dev/val；冻结 exclusion；媒体 group split |
| MULTI | problem 内共享材料；考试内容版权；公开题污染 | 唯一 problem group；来源 manifest；sealed test 建议 |
| OmniGUI | episode 内依赖；UI 隐私；step 不独立 | episode split/bootstrap；媒体隐私审查 |
| MMBench-Dev-CN | CircularEval 重复；公开 dev 污染 | 只留 canonical pass；媒体 group split |
| CCBench | CircularEval 重复；文化口径偏差 | 只留 canonical pass；争议审查与分层报告 |
