# 下一步提示词

执行 **Step L5-A4h6a：正式 tokenized 容量批次双模式零网络 preflight 与连续执行准入**。

本任务已有项目级默认授权，不要再次询问测试、仓库外临时文件、Botzone connector、网页建桌或 DeepSeek 调用的项目授权。系统或浏览器自身要求的确认仍按平台机制处理。只有遇到必须由项目所有者判断的真实页面归属、验证码或页面状态不确定性时，才暂停并提出一个具体问题；等待确认本身不构成批次失败。

## 固定前提

- 仓库：`D:\VsCodeProject\GuanDan`。
- benchmark 契约检查点：`569d5431a83e98a2f32928ded7fcda8846e5a8f0`。
- 正式 seeds：`42001`、`42002`。
- 正式 root：`D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002`。
- 正式 manifest 已使用真实 `ScheduledPair(seed, local_seat, first_strategy, second_strategy)` 路径生成，并在 root 创建前完成 payload、canonical bytes、hash、16 局路径及 16 个唯一 provenance token 的一致性验证。
- root 内的 manifest、九字段初始 `progress.json`、16 个隔离 state 目录及 16 个 completion audit 目标已经原子落盘并回读验证。
- 当前应为 8 对、16 局，rule/deepseek 各 8 局，AB/BA 各 4 对；16 个 state 目录为空，16 个 completion audit 不存在。
- 临时 initial writer 已清理；尚未运行 preflight、connector、网页桌或任何网络请求。
- 正式 manifest 已构成不可重写的批次边界。不得重建、覆盖、补写、迁移或规范化 manifest；不得更换 seed、token、路径、顺序或策略模式。
- 既有 `README.md` 用户改动及其他无关改动不得触碰、暂存或提交。

## 允许范围

本任务以执行和仓库外审计为主。除非发现仓库实现自身存在明确缺陷，否则不要修改仓库代码；不得修改 `engine/`、`agents/`、Botzone 协议、connector、benchmark 或测试来迁就本批次。不要读取或输出 `.env`、URL、API key、Header、Cookie、match ID、token、手牌、prompt、模型响应或逐局请求正文。

## 1. 只读锁定正式批次

先使用互相独立、可审计的命令完成以下检查：

1. HEAD 包含 `569d5431...`，仓库模块来源指向当前仓库；工作区除项目所有者既有改动外没有任务产生的改动。
2. 运行 benchmark 定向 13 项、全量 624 项以及 `git diff --check`。测试计数若因后续既有提交增加，可接受实际更高计数，但不得减少或失败。
3. 仅以 `present` 或精确允许值验证 Botzone URL、DeepSeek key、endpoint、model、timeout=60、retries=0；不得记录配置值或读取 `.env`。
4. 用不会匹配检查命令自身的方式确认没有残留 launcher/connector。
5. 对正式 root 做只读 inventory：manifest 和 progress 各一份；16 个 state 目录存在且为空；16 个 completion audit 不存在；没有临时 writer、临时 manifest、临时 progress 或未知文件。
6. 回读 manifest，验证 canonical JSON/hash 未改变，精确覆盖 seed×seat、8 对/16 局、rule/deepseek 8/8、AB/BA 4/4、连续 pair/game index、16 个唯一合法 token以及每局唯一 state/audit 路径。不得在日志或结论中输出 token。
7. 回读九字段 progress，字段集合必须精确为：`schema`、`version`、`status`、`manifest_sha256`、`total_game_count`、`completed_game_count`、`next_game_index`、`failed_game_index`、`failure_stage`。初始值必须表示 ready、total=16、completed=0、next=1、两个 failure 字段为 null，并绑定当前 manifest hash。

任一只读门槛失败，停止且不得修复正式 artifact。输出 `precondition_failed: formal_capacity_artifact_mismatch`，说明固定低敏原因；不得运行 preflight 或 live。

## 2. 资格验证 progress continuation helper

initial writer 已清理，而后续每局需要更新 progress。先在正式 root 之外创建一个本任务专用、标准库-only 的临时 continuation helper：

- helper 不包含 URL、key、token、seed、正式路径或任何 live 数据；运行参数由调用方传入。
- 只实现严格九字段 progress 校验、允许的状态转换、canonical JSON 和 `O_EXCL temp → write → flush → fsync → close → os.replace → binary readback → temp absent` 原子写入。
- 不实现 manifest serializer，不得写 manifest，也不得从已有 evidence 猜测赛程。
- 先 `py_compile` 并验证项目模块来源，再在 scratch 副本上演练：初始态、连续完成 game 1..16、每个允许 failure stage、跳号/回退/字段缺失/多字段/hash 不符/非法 null/bool 反例。
- 两次 qualification 结果必须逐字段一致，scratch 最终清理；qualification 期间正式 root 必须逐字节不变。
- qualification 失败允许在没有接触正式 artifact、没有网络副作用时修正 helper 后重新资格验证；只有 qualification 通过后才可继续。正式 progress 一旦由 helper 更新，后续失败即停止，不得重写历史状态。

## 3. 双模式零网络 preflight

资格通过后，分别执行恰好一次：

1. `rule --preflight-only`
2. `deepseek --preflight-only`

两次必须使用 manifest 中各自第一局对应的独立空 state 目录，但不得写 completion audit，不得携带 run token 进入网络路径。每次要求：

- 子进程自行退出，exit code 0；stdout 规范化后只有 `preflight_ready`；stderr 为空。
- preflight 前后对应 state 目录为空；其余 15 个 state 目录和全部 completion audit 不变。
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action、`suggest_action_id()` 均为 0。
- 不读取或输出 `.env`、真实配置值、token 或路径。

在正式 root 内原子写入一份新的低敏 `preflight-summary.json`，只保留 schema/version、manifest hash、rule/deepseek exit/readiness、state/layout 守恒、零网络计数、helper qualification hash 与总布尔值；不得包含 seed、token、绝对路径、URL、key 或异常正文。写入后回读并做敏感字段扫描。

若任一 preflight 失败：不得重试另一模式或 live；使用已验证 helper 将 progress 原子转为 invalid，`failure_stage=offline_preflight`，保留 manifest/layout/evidence，输出唯一判定 `botzone_verified_ui_paired_capacity_preflight_invalid`。

若两次均通过：先输出中间判定 `botzone_verified_ui_paired_capacity_preflight_ready`，然后在同一任务内直接进入第 4 节，不再请求项目授权，不新建准备任务。

## 4. 连续执行 16 局

严格按 manifest 的 game index 1..16 串行执行。每局独立 state、completion audit、agent mode 和 run token；不得跳局、并行、重试、补采或复用失败局。

### 大厅与人工门槛

- 大厅中明确属于其他玩家的桌不构成阻塞，直接忽略；不得点击、加入或关闭。
- 明确属于当前账号的旧活动桌时暂停，请项目所有者关闭后继续；不要自行结束该桌。
- 桌归属不确定时只问“是否继续创建本批次新桌”；等待回复不判 invalid。
- 验证码由项目所有者人工完成；等待验证码不判 invalid，也不得让 connector 在等待期间提前退出。

### 每局固定 UI/connector 顺序

1. 获取最新页面 DOM/截图，进入唯一 GuanDan 建桌表单；必要时点击游戏选择浮层中唯一 GuanDan 选项和唯一“创建”，但不得盲点或重复点击。
2. 点击一次“载入上次配置”，设置并 readback：当前 game 的 seed、本家 seat、需要进贡=否、级牌 2、上轮上游/末游 0/3，以及预注册三个 Bot。Bot ID 只在页面内存中使用，不写审计。
3. 第一次 readback 全部匹配后，才以前台可持续会话启动唯一 connector；参数必须来自当前 manifest game：agent、state、audit、run token，timeout 120、max cycles 100、max wall 3600、finished target 1。
4. 等待页面明确显示已连接；connector 在此期间必须仍存活。若页面尚未连接，继续等待合法 long-poll，不要把 idle timeout 当失败。
5. 连接后执行第二次完整 readback；匹配后只点击一次“开始游戏！”。之后 Browser 仅可只读监督，不得点击任何结束、返回、继续、关闭或桌内按钮。
6. 等待同一 connector 自行完成；不得以页面视觉结果代替 completion evidence。
7. 单局证据通过后，才用 continuation helper 将 progress 从完成前缀 N 原子推进到 N+1；随后进入下一局。

### 单局硬门槛

- connector exit 0、`stop_reason=finished_target`。
- requests=responses=Headers 且大于 0；qualified finished=1、normal result=1。
- 非 timeout transport failure=0；idle timeout 仅在 v8 数值、固定 diagnostic 和 benchmark 契约精确守恒时允许。
- 协议 diagnostics/detail/profile 除允许的 timeout 聚合外为空。
- v8 audit 与 v4 minimal finished tombstone 的 run token、mode、路径角色和 manifest game 精确匹配；不得输出 token。
- state 不得有 active/pending/inflight/effect/handler/cache 内容。
- rule 局全部最终来源为 `rule_primary`，model attempts/results/fallback 全为 0。
- deepseek 局至少 1 次 model success；所有 model results 必须为 success，RuleBased fallback=0；来源与决策数守恒。

任一局失败：立即停止，不启动下一局、不重试、不补采。保留该局及此前 evidence；若 progress 仍可验证，原子更新为 invalid，`failed_game_index` 为当前 game，`failure_stage` 使用固定低基数阶段。输出唯一判定 `botzone_verified_ui_paired_capacity_continuation_invalid`。

## 5. 最终聚合与验收

16 局全部通过后：

1. 只读复核 manifest hash、16 份 v8 audit、16 份 v4 tombstone、token/mode/path 归属及 progress 完成前缀。
2. 使用正式 `build_paired_schedule((42001, 42002), ...)` 与 `aggregate_policy_audits()` 聚合完整四座位 schedule。
3. 必须得到 requested/valid=`8/8`，invalid/incomplete/duplicate=`0/0/0`，diagnostics 为空；每个 seat 为 `2/2`，AB/BA=`4/4`。
4. 原子写入低敏 canonical final report，只使用既有 report `to_dict()` 聚合字段；不得包含 seed、token、路径、Bot/match/player 标识、逐局 audit、手牌、prompt 或模型内容。
5. 将 progress 原子更新为 completed：completed=16、next=null、failure 字段为 null。
6. 清理临时 continuation helper；不得删除 manifest、progress、preflight summary、final report、v8 audit 或 tombstone。

唯一成功判定：

```text
botzone_verified_ui_paired_policy_capacity_verified
```

最终报告给出每项门槛、聚合原始整数、Fraction 与 evidence bytes/SHA-256。结果仅是 8 对小容量描述统计，不得表述为显著性、因果收益、动作质量提升或胜率提升，也不得据此默认启用 DeepSeek。
