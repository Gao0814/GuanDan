# 下一步实施提示词

## Step L5-A4d：Botzone 成对容量恢复准入

L5-A4c 小容量批次已停止，唯一判定：

```text
botzone_paired_policy_capacity_invalid
```

### 已封存事实

- 原清单固定为 seed `24001/24002`、四座位、`rule/deepseek` 各 8 局，共 8 对/16 局。
- 第 1 局 rule 完整结束：协议闭环、正常团队胜、26 次 `rule_primary`、模型调用 0。
- 第 2 局 deepseek 完整结束：协议闭环、正常团队胜；24 次决策中 `local_shortcut=15`、`model=9`，9 次模型尝试均 success，fallback=0。
- 第 3 局在人工建桌前以 `poll_malformed` 停止，request/response/Header/finished 和 Agent/模型计数均为 0。
- 第 3 局期间存在项目所有者另建测试桌验证 DeepSeek 的人工操作；该观察没有对应预注册 v7 审计，不得进入容量结果。
- 按预注册规则，任一局失败即停止整批且不重试。因此第 3 局不得重开，第 4–16 局不得继续，前两局也不得移入后续新批次。

原容量根目录、manifest、三份 audit 和 state 必须保持只读，不得清理、改写、补写或作为新批次输入。本步骤不读取其中的对局正文。

### 策略定义封板

新批次比较对象固定为：

```text
rule = 当前部署的 RuleBased 模式
deepseek = 当前部署的 DeepSeek 模式，包括既有 local shortcuts
```

保留 local shortcuts，理由：

1. 它们是当前真实部署策略的一部分，负责唯一 pass、一次出完和已启用的本地开局路径。
2. 它们只从合法动作中选择，可降低模型延迟、超时和调用成本。
3. v7 audit 已分别记录 `local_shortcut`、`model`、两层 fallback 和 model-exposed game，可透明报告模型实际暴露程度。
4. 在容量试验中临时关闭快捷路径会改变 treatment，无法回答“当前可部署 DeepSeek 模式是否优于 RuleBased”。

不得为恢复容量批次修改 DeepSeek Agent、快捷路径、prompt、RAG、fallback、connector 或 benchmark。若未来要评估纯模型因果贡献，应另立 `deployed_deepseek` 与 `forced_model` 消融任务，不得与本批次混合。

### poll_malformed 边界

第 3 局的 `poll_malformed` 发生在 request=0、人工建桌前，并且同一时段存在额外测试桌操作。现有证据不足以归因到 Botzone gateway、poll parser、网络或 connector，也不足以安全放宽 fail-closed。

本步骤：

- 不修改 poll parser；
- 不把 `poll_malformed` 当作空闲成功；
- 不增加自动重试或忽略预算；
- 不根据单次聚合诊断新增协议兼容分支。

若全新、严格单桌批次再次在建桌前出现 `poll_malformed`，立即停止并另立低基数离线诊断任务；不得在容量运行中现场修复。

### 新批次固定条件

永久排除旧 seed `24001/24002`。新批次使用：

```text
25001
25002
```

其余条件保持：

- profile：`botzone_no_tribute_level_2/v1`
- 需要进贡：否
- 当前级牌：2
- 上轮头游/末游：0/3
- `0/2`、`1/3` 位置等级：2/2
- 相同三个对手 Bot 及版本贯穿全部 16 局
- 本家 seat `0..3`
- 每个 `(seed, seat)` 各一局 rule/deepseek
- AB/BA 各 4 对
- runmatch=0，只允许人工网页建桌

### 当前人工前置

在运行任何回归、目录探针、清单或 preflight 前，项目所有者必须提供：

```text
所有历史及额外本地 AI 测试桌已全部结束：是
新容量根目录：D:\VsCodeProject\BotzonePairedCapacity-25001-25002
```

该目录必须由项目所有者预先创建，位于仓库外、当前为空，且不得复用旧容量目录、`BotzoneState` 或 `BotzoneAudit`。

PowerShell 创建方式：

```powershell
$root = "D:\VsCodeProject\BotzonePairedCapacity-25001-25002"
if (Test-Path -LiteralPath $root) {
    throw "目录已存在，请不要清理或复用"
}
New-Item -ItemType Directory -Path $root | Out-Null
(Get-ChildItem -LiteralPath $root -Force).Count
```

最后必须输出 `0`。

### 收到前置后的离线准入

输入齐全后才执行：

1. 验证新目录绝对、仓库外、存在、为空；执行单文件原子写/重命名/删除探针，最终仍为空。
2. 复核 L5-A4a/L5-A4b 检查点及工作区；既有 `README.md` 保持未触碰。
3. 运行：

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

4. 直接调用 `build_paired_schedule((25001, 25002), conditions)`，在新根目录生成不可改写的 canonical manifest；必须为 8 对/16 局、rule/deepseek 各 8、AB/BA 各 4，并记录 bytes/SHA-256。
5. 创建 16 个隔离 state 子目录和 audit 目录；不得把 Bot ID、URL、key、match、牌或模型正文写入 manifest。
6. 使用两个独立空 state 目录，分别执行一次 rule/deepseek 零网络 preflight；均须 exit 0、stdout=`preflight_ready`、stderr/state 空、零网络、无残留。

任一离线门槛失败即停止，不得重试、换 seed、换目录或进入 live。

### 建桌操作约束

后续新批次必须严格串行：

- 同一时刻只能有一个 connector 和一个活动测试桌；
- connector 启动后，只创建 manifest 当前行对应的桌；
- 不得为了检查 DeepSeek、余额、连接状态或动作另建测试桌；
- 不得同时打开第二桌、运行 CLI DeepSeek 对局或其他 Botzone connector；
- 每局结束并确认 connector 退出后，才进入下一行；
- v7 audit 是唯一计分证据，网页人工观察不得替代或补充 audit。

### 验收与授权边界

全部离线门槛通过时唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_ready
```

随后只提出一次新的整批 live 授权问题，不在本步骤联网。授权必须覆盖：16 个串行 connector/人工桌、每局最多 100 次 Botzone GET、DeepSeek 仅在 8 个 deepseek game 中调用且总上限 800、单次 timeout 60 秒、retries 0、每局最长 3600 秒，以及本家未公开手牌和既有决策上下文发送到 `https://api.deepseek.com` 的 `deepseek-v4-flash`。

没有新授权不得启动第一局。即使恢复批次全部完成，也只能形成容量与描述性成对统计，不得直接宣称显著性、因果效果或胜率提升。
