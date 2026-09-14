# 下一任务授权门槛

当前没有待执行的 Coding 任务。三项成功模型后置策略覆盖已经全部退役，seed `47003` evidence 已完成审计和回收，固定 workspace 已由规划 Codex 独立确认为空。

下一候选任务是使用最新 HEAD 运行一局人工配置的 Botzone `deepseek` decision-trace 采样，以新公开决策证据寻找可复现的 prompt、RAG 或策略意图缺口。该任务必须使用项目 Skill `botzone-manual-live`，固定四人、单局、级牌 `2`、无需进贡、玩家1/seat 0，候选 seed 为 `47004`；页面确认“已连接”前不得向项目所有者提示 seed。

完整单局可能达到或超过 10 次真实 DeepSeek 请求，超出 `AGENTS.md` 中“严格少于 10 次免申请”的长期授权。因此当前不得启动 preflight、connector、浏览器监督、建桌或模型请求，也不得把本文件视为 live 执行 Prompt。

拟申请的单局上限：

- 最多一个 connector、一个目标桌、一局。
- `timeout-seconds=120`、`max-cycles=100`、`max-wall-seconds=3600`、`stop-after-finished=1`。
- 仅对本次进程设置 `DEEPSEEK_MAX_RETRIES=0`；每个本家决策最多一次模型请求，整任务真实 DeepSeek 外部请求硬上限为 100。
- 显式生成 completion audit、history、acknowledged decision trace、state/finished tombstone、stdout 和 stderr；全部保留供规划复审。
- 不运行容量评测，不修改仓库，不因输赢、source 分布或样本质量创建第二桌。

只有项目所有者明确授权“seed `47004` 单局 DeepSeek live，真实模型请求上限 100、重试 0”后，规划 Codex 才能把本文件替换为可直接交给执行 Codex 的完整 live Prompt。若不授权，则保持空 workspace，不启动任何外部执行。
