# 下一步提示词

执行 **Step L5-A4h6b：continuation helper 资格覆盖恢复与双模式零网络 preflight**。

本任务已有项目级默认授权，不要再次询问测试、仓库外 qualification/scratch/state/audit 文件或零网络 preflight 的授权。系统自身要求的权限确认仍按平台机制处理。本步骤严格零网络，不启动 connector、不打开或操作 Botzone 网页、不调用 DeepSeek 动作接口。

## 已确认状态

- 正式 seeds：`42001`、`42002`。
- 正式 root：`D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002`。
- 正式 manifest、九字段初始 progress 与 16 局隔离布局已原子落盘并只读锁定。
- 16 个 state 目录均为空，16 个 completion audit 均不存在；没有 `preflight-summary.json`、临时或未知 artifact。
- manifest/progress/layout 在上一步前后完全不变；没有网络、connector、Agent 或模型调用。
- root 外唯一 continuation helper 已建立并编译。上一步两次 scratch 结果虽可重复，但 qualification driver 没有覆盖全部要求的 invalid 转换与反例拒绝路径，因此判定 `precondition_failed: continuation_helper_qualification_failed`。
- 该失败只属于 root 外资格证明不完整，不使正式批次、seed 或 root 失效；不得创建新 manifest、progress、helper、seed 或正式 root。
- 不得修改仓库代码、测试、`README.md` 或无关文件；不得读取或输出 `.env`、URL、API key、Header、Cookie、token、绝对 evidence 路径、手牌、prompt 或模型响应。

## 1. 再次只读锁定正式 evidence

开始前记录正式 root 的低敏 inventory 与 manifest/progress bytes/SHA-256，并与上一步封存状态比较：

- manifest canonical bytes/hash 不变；
- progress 仍为精确九字段 initial ready：total=16、completed=0、next=1、两个 failure 字段为 null；
- 16 个 state 为空，16 个 completion audit 不存在；
- 无 preflight summary、临时文件、未知 artifact 或残留 connector/launcher。

不一致时输出 `precondition_failed: formal_capacity_artifact_mismatch`，不得修复或继续。

## 2. 只加固现有 qualification 覆盖

复用现有 helper，不创建第二个 helper，不把任何 qualification 文件写入正式 root。先只读检查 helper：

- 九字段 schema 与当前正式 progress 精确一致；
- 固定 failure-stage allowlist 恰好 9 项、无重复；
- helper 不包含 manifest serializer、正式 seed/token/path、网络、connector、Agent 或 DeepSeek 逻辑；
- helper source bytes/SHA-256 在资格开始后锁定。

允许在正式 root 外创建或修正唯一 qualification driver。driver 只调用现有 helper，并生成不含 stage 文本、路径、seed/token 的低敏 coverage bitmap/count/hash。不得靠手工声称覆盖，必须由 case registry 驱动并在运行结束时证明“预期 case 集合 = 实际执行集合”。

### 必须覆盖的合法转换

1. initial ready 状态精确校验。
2. game 1..16 连续完成：每次 completed 只加 1，next 精确前移；第 16 局后进入 completed，next 与 failure 字段为 null。
3. 对 helper 锁定的 9 个 failure stage，在每个 next game index 1..16 上分别执行一次 ready → invalid，共 `9 × 16 = 144` 个合法 invalid 转换；failed index 必须等于转换前 next，completed 保持原前缀。
4. 合法转换均验证 canonical JSON、原子写入九阶段、binary readback、临时文件不存在及 source progress 被预期替换。

### 必须覆盖的拒绝路径

每个反例都必须在写入或 replace 前被拒绝，原合法 progress bytes/SHA-256 不变：

- top-level 非 object；缺任一九字段；逐个增加未知字段；
- schema/version/status 类型错误或未知值；
- `bool` 冒充所有整数位置；字符串、float、负数和越界整数；
- manifest hash 类型、格式或绑定值错误；total 不为 16；
- ready/completed/invalid 三种状态下 completed、next、failed index、failure stage 的全部 null/非 null 组合矛盾；
- 完成跳号、回退、重复提交、越过 16、从 completed 再写、从 invalid 再写；
- failed index 不等于当前 next；未知 failure stage；failure stage 非字符串；
- temp 已存在，以及 write/flush/fsync/close/replace/readback 任一注入失败时不得留下目标半写或临时文件。

对可组合矩阵采用表驱动生成，输出每类 expected/executed/rejected/pass 原始整数及 coverage hash。禁止只抽取代表样本来代替上述穷举项。

## 3. 两次独立 qualification

qualification driver 先 `py_compile`，再使用两个全新的 root 外 scratch 目录运行两次。要求：

- 两次 exit 0；case registry、分类计数、coverage bitmap/hash 与最终结构 hash逐字段一致；
- 9 个 failure stage、16 个 game index 和 144 个合法 invalid 转换全部命中；
- 所有拒绝 case 均命中且原 bytes/hash 不变；
- 原子故障注入均完成清理；两个 scratch 最终为空并删除；
- helper source hash 和正式 root inventory 前后不变；
- network/transport/connector/Agent/model 计数均为 0。

资格 driver 自身若在导入/解析/参数阶段失败且未执行 case，可在本任务内修正后重新开始两次全新 qualification。若 case 已执行但覆盖或 helper 行为不满足契约，停止并输出：

```text
precondition_failed: continuation_helper_qualification_recovery_failed
```

不得运行 preflight，不得写正式 progress 或 summary。

## 4. 双模式零网络 preflight

两次 qualification 全部通过后，按顺序各执行恰好一次：

1. `rule --preflight-only`
2. `deepseek --preflight-only`

使用 manifest 中各模式第一局对应的空 state 目录。每次必须使用项目 `.venv` 和当前进程显式配置、禁止读取 `.env`；仅验证配置 present/锁定元数据。要求：

- 30 秒内自行 exit 0；stdout 规范化为唯一 `preflight_ready`；stderr 空；
- state 前后为空，其余 state/audit 不变；不携带 run token，不写 completion audit；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action、`suggest_action_id()` 全部为 0；
- 结束后无残留进程。

rule 失败时不执行 deepseek；任一 preflight 失败不重试、不 live。使用已资格验证的 helper 将正式 progress 原子转为 invalid，`failed_game_index=1`、`failure_stage=offline_preflight`、completed=0、next=1，并输出：

```text
botzone_verified_ui_paired_capacity_preflight_invalid
```

## 5. 成功证据

双 preflight 通过后，在正式 root 原子创建唯一低敏 `preflight-summary.json`，只保留固定 schema/version、manifest/helper/coverage hash、qualification 分类原始整数、两次 preflight 固定布尔值、inventory 守恒和零网络计数。不得包含 stage 名列表、seed、token、绝对路径、URL、key、命令行或异常正文。

成功时正式 progress 保持 initial ready，不运行 connector、网页桌或第 1 局。唯一判定：

```text
botzone_verified_ui_paired_capacity_preflight_ready
```

报告 summary 的 bytes/SHA-256、qualification 完整覆盖计数、双 preflight 门槛及全部零网络计数。下一步再按 manifest 开始 16 局 live，不请求新的项目授权。
