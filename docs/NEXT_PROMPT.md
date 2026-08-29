# 下一步提示词

执行 **Step L5-A4h7：按已封存 manifest 自动完成 Botzone verified-UI 8 对 / 16 局正式容量批次**。

这是正式 live 执行任务，不要重新规划、重建布局、重跑 qualification/preflight 或再拆分准备任务。项目所有者已默认授权本批次所需的 connector、Botzone 网页点击、人工建桌、DeepSeek 调用和仓库外 evidence 写入；不要重复询问项目级授权。系统/浏览器自身权限确认仍按平台机制处理。只有验证码、登录失效、当前账号旧桌或页面归属确实不确定时才暂停提出一个具体问题；等待用户处理不构成批次失败。

## 1. 固定批次与已通过前置

仓库：

```text
D:\VsCodeProject\GuanDan
```

正式 root：

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002
```

固定 evidence：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `capacity-manifest.json` | 4661 | `5989a6dc07441c94b02725a31b29706d9708311ce7eee597e82b96b47921b4ff` |
| `progress.json`（initial） | 277 | `0517765bcdd4241c01eaca29bbb9d29e900a0890649ea3c45e5e251cc59745e2` |
| `preflight-summary.json` | 2273 | `32a9cf1adfdc881037aea6adb8f594a51876a958df88fc0a4432ddf55370cad9` |

已验证且不得重跑：

- helper/driver `py_compile` 与两次独立 qualification 全通过，expected/executed=`269/269`。
- 合法写入 161：initial 1、连续完成 16、9 stages×16 indices=144。
- 拒绝用例 108 全通过；coverage SHA-256 `1c3d211f7b8989b707de2b1b36252002c72799f26163d2157fe4180fef017a33`；结构 SHA-256 `f31ef00f404a874864b967af11451f7ba0f35f44b74877d8d8150a03a2e3b5b0`。
- rule/deepseek preflight 各实际启动一次并 exit 0、唯一 `preflight_ready`、stderr 空；全部网络/connector/Agent/model 计数为 0。
- 当前 16 个 state 目录均为空，16 个 completion audit 均不存在；正式 progress 仍为 initial ready。

已验证 progress helper：

```text
C:\Users\86166\AppData\Local\Temp\botzone_progress_helper.py
```

当前 helper：9156 bytes，SHA-256 `de67b2d0e78aab328c6ca862981f6a8fa28a986d5e63ca7128669f681c492cbe`。

qualification driver 只作证据保留，不在 live 中调用：13390 bytes，SHA-256 `94c55ba99bfa1f4a3efd97f8eeb469a753690f08e722c35a2899cf1e71fd5a5b`。

不得改写 manifest/preflight summary，不得更换 seeds、token、路径、mode 或 game 顺序，不得读取或输出 `.env`、URL、API key、Header、Cookie、run token、Bot ID、match ID、手牌、prompt、reasoning 或模型响应正文。

## 2. 固定赛程

从 manifest 读取每局的真实 `state_dir`、`audit_path` 和 `run_token`，不得在日志或回复中输出 token。低敏赛程如下：

| Game | Pair | Seed | Seat | Agent |
|---:|---:|---:|---:|---|
| 1 | 1 | 42001 | 0 | rule |
| 2 | 1 | 42001 | 0 | deepseek |
| 3 | 2 | 42001 | 1 | deepseek |
| 4 | 2 | 42001 | 1 | rule |
| 5 | 3 | 42001 | 2 | rule |
| 6 | 3 | 42001 | 2 | deepseek |
| 7 | 4 | 42001 | 3 | deepseek |
| 8 | 4 | 42001 | 3 | rule |
| 9 | 5 | 42002 | 0 | deepseek |
| 10 | 5 | 42002 | 0 | rule |
| 11 | 6 | 42002 | 1 | rule |
| 12 | 6 | 42002 | 1 | deepseek |
| 13 | 7 | 42002 | 2 | deepseek |
| 14 | 7 | 42002 | 2 | rule |
| 15 | 8 | 42002 | 3 | rule |
| 16 | 8 | 42002 | 3 | deepseek |

固定 profile/budget：无贡、级牌 2、沿用同一上轮名次 profile 和同一三个非本家 Bot；poll timeout 120 秒、max cycles 100、max wall 3600 秒、完成 1 局即停；DeepSeek timeout 60 秒、retries 0。

## 3. 启动前唯一只读门槛

只执行一次快速检查，不重跑测试或 preflight：

- HEAD 包含 benchmark 检查点 `569d5431a83e98a2f32928ded7fcda8846e5a8f0` 与 run provenance 检查点 `45d34f0d443847aea527929e2a7c0ebf9e4bdd5a`；工作区无任务产生的改动。
- 上述 manifest/preflight summary bytes/SHA-256 不变；progress 为 initial ready 并绑定 manifest hash。
- helper bytes/SHA-256 匹配；16 state 空、16 completion audit 不存在；无残留 connector/launcher。
- 当前进程只以 present/match 核对 Botzone URL、DeepSeek key、endpoint/model、timeout 60、retries 0；`PYTHON_DOTENV_DISABLED=1` 在子进程启动前生效。

失败时输出 `precondition_failed: formal_live_admission_mismatch`，不得修复正式 artifact或启动第 1 局。

## 4. 大厅和浏览器控制规则

优先使用现有已登录 Botzone 浏览器标签页并读取最新 DOM/截图，不根据旧截图点击。

- 大厅中明确属于其他玩家的桌直接忽略，不点击、加入或关闭。
- 明确属于当前账号的旧活动桌时暂停，请用户关闭后继续；不自行结束。
- 归属无法判断时只问“是否继续创建本批次新桌”；用户确认后继续，不能把等待或确认判为 invalid。
- 遇到验证码时停在验证码页面，请用户完成后继续；不启动 connector等待验证码。
- 每局只允许创建一个 GuanDan 桌，只点击一次最终“开始游戏！”。
- 对局开始后 Browser 完全只读，不点击结束、退出、返回、继续、关闭或桌内任何按钮。

## 5. 每局严格执行顺序

按 game 1→16 串行；前一局 evidence 和 progress 均通过后才开始下一局。不得并行、跳局、重试、补采或复用失败局。

### A. 准备网页表单

1. 从主页进入创建游戏桌，选择唯一 GuanDan 选项并点击唯一“创建”；若出现验证码，等待用户完成。
2. 进入 GuanDan 表单后点击一次“载入上次配置”。
3. 按当前 manifest game 设置 seed 和本家 seat；锁定“需要进贡=否”、级牌 2、同一上轮名次 profile。
4. 只在浏览器内存中确认三个非本家 Bot 槽均已填充且与载入配置一致；不复制或持久化 Bot ID。
5. 第一次 readback 必须逐项匹配 seed/seat/no-tribute/level/profile/Bot 槽；不匹配时可在提交前修正并再次 readback，不能启动 connector。

### B. 启动唯一持续 connector

第一次 readback 通过后，使用当前 game manifest 的 `agent_mode`、`state_dir`、`audit_path`、`run_token` 启动一个前台 PTY connector。必须取得可持续轮询的 session ID；命令保持同一会话运行，不使用会提前返回的 detached launcher，也不创建第二个 connector。

等价参数必须为：

```text
python -m integrations.botzone
--agent <manifest agent_mode>
--state-dir <manifest state_dir>
--run-token <manifest run_token>
--timeout-seconds 120
--max-cycles 100
--max-wall-seconds 3600
--stop-after-finished 1
--audit-file <manifest audit_path>
```

connector 未保持运行、启动即退出或没有 session ID 时，不提交网页桌；按 `connector_start` 失败处理。

### C. 连接确认和唯一提交

1. 轮询同一 connector session，并只读观察页面直到明确显示“已连接”。正常 long-poll idle timeout 不构成失败。
2. 页面连接后执行第二次完整 readback；全部匹配才点击一次“开始游戏！”。
3. 点击后 Browser write count 必须保持 0，只读监督页面是否进入和完成对局。
4. 等待同一 connector 自行退出，不使用页面结果代替 completion evidence。

### D. 单局 evidence 硬门槛

每局必须全部满足：

- connector exit 0，`stop_reason=finished_target`；
- request=response=Header 且大于 0；qualified finished=1、normal result=1；
- 非 timeout transport failure=0；idle timeout 仅在 v8 timeout 数值和唯一固定 diagnostic 精确守恒时允许；
- 其他 diagnostics/detail/profile 为空；
- v8 completion audit 的 mode/run token 与 manifest game 匹配；
- state 只剩一份 v4 minimal finished tombstone，其 run token 与 audit/manifest 匹配；无 active、pending、inflight、effect、handler 或 cache；
- rule 局全部最终来源为 `rule_primary`，model attempts/results/fallback 全为 0；
- deepseek 局至少 1 次 model success，所有 model result 均为 success，RuleBased fallback=0；决策来源、模型尝试和结果守恒；
- audit/tombstone 不包含敏感字段，且记录各自 bytes/SHA-256。

### E. 原子推进 progress

单局 evidence 通过后，从当前 `progress.json` 读取并构造唯一下一状态：completed 只增加 1；game 1..15 为 running 且 next=completed+1；game 16 为 completed 且 next=null；failure 字段为 null。

通过 `importlib` 从固定路径加载已验证 helper，并调用 `atomic_progress_write()`；传入 manifest SHA-256。写后回读 canonical JSON，确认无 `.tmp`。不得手工覆盖 progress，不调用 qualification driver。

progress 更新失败时以 `progress_write` 处理，不启动下一局。

## 6. 失败处理

验证码/登录/大厅归属等待不是失败。其余任一局门槛失败：

1. 立即停止，不启动下一局、不重试当前局、不创建第二桌或第二 connector。
2. 保留当前及此前全部 audit/state，不删除 tombstone或失败 session。
3. 若 helper 和当前 progress 仍可验证，用 helper 原子转为 invalid；failed index 为当前 game，stage 从以下固定值选择：`lobby_gate`、`ui_readback`、`connector_start`、`table_submit`、`connector_run`、`evidence_validation`、`progress_write`。
4. 若 progress 自身不可验证，不覆盖它，只报告失败边界。

唯一失败判定：

```text
botzone_verified_ui_paired_policy_capacity_invalid
```

报告已完成前缀、失败 game/stage 和低敏聚合；不输出 token、路径、Bot/match ID、手牌或模型内容。

## 7. 全批次聚合

game 16 的 progress 成功进入 completed 后：

1. 只读复核 manifest/preflight summary 不变，16 份 v8 audit、16 份 v4 tombstone 与每局 token/mode/path一一对应。
2. 使用正式 `build_paired_schedule((42001, 42002), ...)` 和 `aggregate_policy_audits()` 聚合完整四座位赛程，不自行缩小 selected seats。
3. 必须得到 requested/valid=`8/8`，invalid/incomplete/duplicate=`0/0/0`，diagnostics 为空；每 seat=`2/2`，AB/BA=`4/4`。
4. 使用既有 report `to_dict()` 原子写入 `paired-report.json`；报告不得包含 seed、token、路径、Bot/match/player 标识、逐局 audit、牌、动作或模型正文。
5. 回读 canonical report、验证临时文件不存在并做敏感字段扫描。helper/driver 保留，不删除正式 evidence。

聚合失败时不得改写已 completed 的 progress；输出同一 invalid 判定，failure stage=`final_aggregate`。

## 8. 成功判定

唯一成功判定：

```text
botzone_verified_ui_paired_policy_capacity_verified
```

最终报告列出：16 局逐局低敏门槛、audit/tombstone bytes/SHA-256、8 对聚合原始整数与 Fraction、RuleBased/DeepSeek 正常胜负和 score buckets、DeepSeek model exposure/success/fallback 聚合，以及 manifest/preflight summary/final report hash。

该结果仅是固定对手、两个 seed、四座位、8 对的小容量描述统计，不得表述为显著性、因果收益、动作质量提升或胜率提升，也不得据此修改默认策略。
