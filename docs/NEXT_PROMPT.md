# 下一任务提示词

## Step L5-A4f2：项目所有者前台启动的单对策略 pilot

L5-A4f1 的 Codex 托管 pilot 不再继续。项目所有者随后在 VS Code PowerShell 中使用现有 connector 命令完成了一局人工无贡 DeepSeek 对局；固定证据已只读核验：

- v8 audit：804 bytes，SHA-256 `ee747bc22d7eaae5003cb4e59480384366059b3287e342498e6fcbcdfdf236d1`；
- exit `0`，stop reason=`finished_target`；
- requests/responses/Headers=`27/27/27`，qualified finished=`1`；
- transport failure=`0`；一次 long-poll timeout 按现有契约只计 idle timeout，不导致失败；
- agent mode=`deepseek`，决策 `local_shortcut=9`、`model=17`；模型结果 `success=17`，RuleBased fallback=`0`；
- 正常四人终局，本家团队负，score bucket=`score_0`；
- state 仅有一份 v4 最小 finished tombstone，run token 形状合法且与 v8 audit 一致。

唯一判定：

```text
botzone_owner_operated_deepseek_manual_smoke_verified
```

该结果证明项目所有者前台启动路径能够完成 Botzone/DeepSeek 协议闭环，但不证明 DeepSeek 优于 RuleBased。

### 目标

使用项目所有者已经成功验证的 PowerShell 前台启动方式，完成一个同条件 RuleBased/DeepSeek 配对 pilot。Codex 只负责准备固定目录/命令、监督审计和聚合，不托管 connector 长进程，不使用 launcher 或 runmatch。

### 固定条件

- pair seed：`31001`
- 本家座位：`0`
- 需要进贡：`否`
- 级牌：`2`
- 对手：两局必须选择完全相同的三个现有 Bot 和相同座位
- 顺序：game 1=`rule`，game 2=`deepseek`
- 每局最多 100 次 local-AI GET
- poll timeout：120 秒
- wall：3600 秒
- 完成 1 局即停
- DeepSeek timeout/retries：60 秒 / 0
- 不调用 runmatch，不创建额外测试桌，不重试失败局

### 仓库外布局

新根目录：

```text
D:\VsCodeProject\BotzoneManualPair-31001
```

固定子目录：

```text
game-01-rule\state
game-01-rule\audit\completion.json
game-02-deepseek\state
game-02-deepseek\audit\completion.json
pair-manifest.json
```

run token：

- game 1 rule：`73ee1e60f7c78de725d22fc0cf66f904`
- game 2 deepseek：`80d24f9af14aec8000f1a2928666c9ca`

token 不得输出到最终报告、浏览器、Header、Agent、DeepSeek 或聚合结果。

### 执行顺序

1. 只读确认检查点 `45d34f0d443847aea527929e2a7c0ebf9e4bdd5a`、`31e2fa5a474a377baa3fb80a4a427766623b96c7`、`e1b4e14f2806b962c16a08434f8fef589bf9630b` 均为当前 HEAD 祖先；不得清理项目所有者已有 README 或其他无关改动。
2. 确认没有残留 connector，且项目所有者已关闭所有旧测试桌。
3. 新根目录必须不存在。原子创建固定 manifest 和四个空目录；manifest 只记录 pair/seed/seat/mode/order/profile/token，不记录 Bot ID、URL、密钥或账号信息。
4. 为 game 1 输出一条可直接粘贴到 VS Code **PowerShell** 的完整单行 rule connector 命令。必须使用显式绝对 state/audit 路径，不使用跨终端 `$state/$audit/$token` 临时变量。
5. 项目所有者运行命令；终端保持无提示符后，页面确认已连接，再人工创建唯一无贡桌。对局结束后只读验收 game 1 v8/v4 evidence。未完成验收前不得启动 game 2。
6. game 1 通过后关闭其网页桌，为 game 2 输出完整单行 deepseek connector 命令；同样先连接后建桌，并保持 seed、seat、三个对手、桌面设置完全一致。
7. game 2 结束后严格验收两份 audit/tombstone/token，并调用现有 `evaluation.botzone_policy_benchmark` 在内存中聚合这一对；不把原始 audit、seed、token、Bot/match/player 标识写入聚合报告。
8. 不删除两份 tombstone；完成后另行安排一次精确清理。

项目内计划操作沿用常驻默认授权，不再询问项目授权。项目所有者在本地 PowerShell 和网页中自行执行命令/建桌时，不需要 Codex 代为点击。

### 单局门槛

两局分别必须满足：

- connector exit `0`，stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- finished qualified=`1`，正常结果=`1`；
- transport failures=`0`；long-poll timeout 可以非零，但只能按 timeout/idle 类别守恒，不能出现其他 transport failure；
- 除与 timeout 计数一致的 `transport_timeout` 外，无协议 diagnostics/detail/profile；
- v8 audit、v4 最小 tombstone 与该局 manifest token 一致；
- state 不含 active session、pending response/effect、handler 或 cache；
- 无残留 connector。

策略门槛：

- rule：`agent_mode=rule`，模型尝试/fallback=`0`，最终决策均来自 rule primary；
- deepseek：`agent_mode=deepseek`，至少一次 model success，模型结果只允许 success，RuleBased fallback=`0`，来源/尝试/结果守恒。

### 判定

全部门槛通过：

```text
botzone_owner_operated_single_pair_capacity_verified
```

输出只允许描述这一对的 RuleBased/DeepSeek 正常结果、score bucket、模型暴露与 existing benchmark 聚合；不得把单对结果表述为显著性、因果、策略增益或胜率结论。

任一局失败：

```text
botzone_owner_operated_single_pair_capacity_invalid
```

失败时立即停止，不重试该局、不继续下一局、不复用 seed/root。保留原 evidence，不增加诊断载体。

### 边界

- 本步不修改 engine、agents、integration、evaluation、tests、配置或上传 Bot。
- 不读取或输出 `.env`、URL、API key、Header、Cookie、Bot/match/player ID、手牌、prompt、RAG 原文、模型响应或逐手动作。
- 本步不恢复 16 局批次；只有该单对操作和 evidence 流程通过后，才使用全新 seed/root 规划小容量恢复。
