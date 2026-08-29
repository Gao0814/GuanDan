# 下一步提示词

继续执行 **Step L5-A4h6a：continuation helper 双次资格演练与双模式零网络 preflight**。

本任务已有项目级默认授权，不要再次询问测试、仓库外 scratch/state/audit 文件或零网络 preflight 的授权。系统自身要求的权限确认仍按平台机制处理。本步骤严格零网络，不运行 connector、不打开或操作 Botzone 网页、不调用 DeepSeek 动作接口。

## 已完成且不得重复

- 正式 seeds：`42001`、`42002`。
- 正式 root：`D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002`。
- 正式 manifest 与九字段初始 progress 已存在并通过原子回读；manifest 已构成不可重写的批次边界。
- 正式布局已只读锁定：manifest/progress 各一份，16 个 state 目录均为空，16 个 completion audit 均不存在，没有临时或未知 artifact。
- 8 对/16 局、rule/deepseek 8/8、AB/BA 4/4、四座位与 16 个唯一 provenance token 已验证。
- root 外的标准库-only continuation helper 已建立并编译通过；不得重新创建第二个 helper，不得把 helper 移入正式 root。
- 尚未运行任何 preflight、connector、网页桌、Botzone GET、DeepSeek request 或其他网络请求。
- 不得修改、重建、覆盖、格式化或补写正式 manifest；不得更换 seed、token、路径、顺序或策略模式。
- 不得修改仓库代码、测试、`README.md` 或无关文件；不得读取或输出 `.env`、URL、API key、Header、Cookie、token、绝对 evidence 路径、手牌、prompt 或模型响应。

## 1. 锁定执行前 inventory

在第一次 qualification 前、第二次 qualification 后以及两个 preflight 后，分别记录正式 root 的低敏 inventory，并要求完全一致，唯一允许新增的是最终 `preflight-summary.json`：

- manifest bytes/SHA-256 与 canonical JSON 不变；
- progress bytes/SHA-256 与九字段初始值不变；
- 16 个 state 目录均为空；
- 16 个 completion audit 均不存在；
- 不存在临时 manifest/progress、未知文件或残留 connector/launcher；
- 不输出 seed、token、路径或配置值。

若执行前 inventory 与已封存状态不一致，立即停止，输出：

```text
precondition_failed: formal_capacity_artifact_mismatch
```

不得修复正式 artifact，也不得运行 qualification 或 preflight。

## 2. continuation helper 双次资格演练

复用已建立并编译的唯一 helper。先只读确认其位于正式 root 外、没有第二套 manifest serializer、没有 URL/key/token/seed/正式路径/live 数据，也没有网络、connector、Agent 或 DeepSeek 导入。

在两个全新的 root 外 scratch 目录中各运行一次完全相同的 qualification。每次只对 scratch 中的合成 manifest hash 与 progress 副本操作，覆盖：

1. 精确九字段初始 ready 状态。
2. 连续 `completed_game_count=0..16` 的全部合法转换；每次只允许前缀加一，不允许跳号、回退或重复提交。
3. completed 最终态：completed=16、next=null、两个 failure 字段为 null。
4. 每个预注册固定 failure stage 的 invalid 转换，要求 failed game 与当前 next game 一致。
5. 缺字段、多字段、bool 冒充整数、非法 schema/version/status/null、越界计数、hash 不匹配、跳号、回退、非法失败索引与已有 invalid/completed 再写入等反例。
6. 每次合法写入严格执行 `O_EXCL temp → write → flush → fsync → close → os.replace → binary readback → temp absent`。
7. 每个非法输入必须在写入前失败，原合法 progress bytes/SHA-256 不变。

两次 qualification 必须：

- exit 0，逐字段结果一致；
- 生成相同的低敏结构 hash；
- scratch 最终清理；
- 正式 root inventory 全程不变；
- network/transport/connector/Agent/model 计数均为 0。

如果 helper 自身存在纯 qualification 缺陷，且尚未接触正式 progress，可在本任务内最小修正现有 helper 后重新从两次全新 scratch 资格演练开始；不得新建第二个 helper。若无法通过，输出：

```text
precondition_failed: continuation_helper_qualification_failed
```

清理 scratch，保留 helper 和正式 root，不运行 preflight。

## 3. rule/deepseek 双模式零网络 preflight

helper 双次资格通过后，先以低敏字段记录 helper bytes/SHA-256 与 qualification 结构 hash。随后按顺序各执行恰好一次：

1. `rule --preflight-only`
2. `deepseek --preflight-only`

使用 manifest 中各模式第一局对应的空 state 目录；不得写 completion audit，不得携带或输出 run token。每次要求：

- 使用项目 `.venv` 与当前进程已注入配置，不读取 `.env`；
- 仅验证 Botzone URL/key 为 present，endpoint/model 为锁定值，timeout=60、retries=0，不记录真实值；
- 子进程在 30 秒内自行退出，exit code 0；
- stdout 规范化后精确为单行 `preflight_ready`，stderr 为空；
- 对应 state 在前后均为空，其余 15 个 state 与全部 completion audit 不变；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action、`suggest_action_id()` 全部为 0；
- preflight 进程结束后没有残留 launcher/connector/Python 子进程。

rule preflight 失败时不得执行 deepseek preflight；任一模式失败均不得重试、不得启动 live。使用已验证 helper 将正式 progress 原子转为 invalid：

- `failed_game_index=1`
- `failure_stage=offline_preflight`
- completed=0，next=1

保留 manifest、布局与失败证据，输出唯一判定：

```text
botzone_verified_ui_paired_capacity_preflight_invalid
```

## 4. preflight summary 与成功判定

两种模式均通过后，在正式 root 中原子创建唯一 `preflight-summary.json`。只允许包含：

- 固定 schema/version；
- manifest SHA-256；
- helper SHA-256 与 qualification 结构 hash；
- 两次 qualification 的 exit、一致性、scratch 清理与零网络布尔值；
- rule/deepseek preflight 的 exit、ready、stderr-empty、state-empty 与零网络布尔值；
- 正式 inventory 守恒布尔值；
- 总布尔值。

不得包含 seed、token、绝对路径、URL、key、环境值、异常正文、命令行、玩家/对局标识或任何逐局内容。写入后回读 canonical JSON，验证临时文件不存在并执行敏感字段扫描。

成功时保持正式 progress 仍为初始 ready，不运行 connector 或网页桌，不进入第 1 局。唯一判定：

```text
botzone_verified_ui_paired_capacity_preflight_ready
```

最终报告列出 manifest/progress/inventory 未变化、两次 qualification 和双 preflight 的固定门槛、`preflight-summary.json` 的 bytes/SHA-256，以及所有网络/connector/Agent/model 计数为 0。下一步才进入按 manifest 串行执行 16 局的 live 任务；不要在本步骤请求新的项目授权。
