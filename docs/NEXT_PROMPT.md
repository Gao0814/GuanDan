# 下一步实施提示词

## Step L5-A4e5：tokenized Botzone 成对容量批次

L5-A4e4 已完成：

```text
botzone_paired_policy_tokenized_capacity_preflight_ready
```

### 固定证据

- 实现检查点 `45d34f0d443847aea527929e2a7c0ebf9e4bdd5a` 范围正确；无 connector 残留。
- 新容量根：`D:\VsCodeProject\BotzonePairedCapacity-26001-26002`。
- manifest：3635 bytes，SHA-256 以已落盘 preflight summary 中的完整值为准；项目所有者报告为 `f1793c…63241`。
- 赛程：16 个唯一 token、8 对/16 局、rule/deepseek 各 8、AB/BA 各 4、四座位各 2 对。
- 16 个 state 目录均为空；16 个 game audit 目标均不存在。
- rule/deepseek 各一次带 token 的零网络 preflight 均 exit 0、stdout=`preflight_ready`、stderr/state 为空。
- preflight summary：653 bytes，SHA-256 报告为 `785ff0…d995a`；全部网络、transport、connector、Agent 与模型计数为 0。
- 仓库未修改，既有 `README.md` 改动未触碰。

项目所有者常驻默认授权覆盖本批次 Botzone 与 DeepSeek 请求，不得再次询问授权。只在需要人工创建/确认每张网页无贡桌时给出操作提示。

### 批次预算与不变量

- 严格按 manifest 顺序串行执行 16 局，不得跳局、换序、补采或重试。
- 每局一个 Python connector、一个预注册 state、一个预注册 v8 audit、一个唯一 token；不得并行第二 connector 或第二桌。
- 总 Botzone GET 上限 1600；DeepSeek physical/logical request 上限各 800。
- 每局 connector：最多 100 cycles、poll timeout 120 秒、wall 3600 秒、`stop_after_finished=1`。
- DeepSeek：`https://api.deepseek.com`、`deepseek-v4-flash`、timeout 60 秒、retries 0。
- 固定无贡、级牌 2、manifest seed/seat、相同三个对手 Bot 及版本、相同上轮头游/末游和双方等级 profile。
- 保留实际部署策略：DeepSeek 模式允许 local shortcuts；v8 audit 单独统计模型暴露和 fallback。
- 禁止 runmatch、额外人工测试桌、CLI DeepSeek 对局、探测请求、参数调整和旧批次 artifact 读取。

### 批次进度

1. 开始前原子创建固定 `capacity-progress.json`，拒绝覆盖。只记录 schema/version、manifest hash、总局数、下一 game index、已完成局数、固定阶段、每局 audit/tombstone hash 与门槛布尔值；不得记录 token、seed、seat、Bot/match/player、路径、牌、prompt/response 或模型正文。
2. 每局完成并验收后原子更新一次；仅允许在两局之间依据该文件恢复任务。
3. 任务/终端中断发生在 connector 启动后且该局未完成验收时，整批 invalid；不得把进度文件用于重启该局。
4. progress 与 manifest 不一致、已有未知字段、game audit/state 与已完成计数不一致时立即停止，不修复。

### 每局执行协议

1. 从 manifest 读取当前 game 的 mode、seed、seat、相对 state/audit 与 token；不在聊天或控制台输出 token。
2. 启动前确认：目标 audit 不存在、state 为空、没有其他 Python connector、没有活动/旧测试桌。若只缺项目所有者确认“已准备立即创建下一桌”，直接请求该操作确认，不称为授权。
3. 使用项目 `.venv\Scripts\python.exe`、`PYTHON_DOTENV_DISABLED=1`、当前 mode/state/audit/token 启动唯一 connector，并保留真实子进程句柄；禁止以进程名模糊搜索代替句柄。
4. 监控子进程并等待 Botzone 页面显示“已连接”。在提示建桌前再次确认子进程存活、state 为空、audit 不存在。
5. 向项目所有者输出当前 game index、manifest seed、local seat、策略模式和固定无贡设置，提示立即创建唯一网页测试桌并回复“已进入对局”。不得输出 token、连接 URL 或密钥。
6. 等待人工操作期间持续监控子进程。若在收到“已进入对局”前退出，立即提示不要建桌或关闭刚创建的桌，并判整批 invalid；不得重启该局。
7. 收到进入确认后继续持有进程，直到其自行退出或达到固定 wall limit；不得启动第二进程。
8. 该局只有同时满足以下条件才有效：exit 0、`finished_target`、request=response=Header 且大于 0、qualified finished=1、零 transport failure/timeout、空 diagnostics/detail/profile、正常四人结果、v8 audit 严格合法、v4 最小 tombstone 严格合法、audit/tombstone token 均与 manifest 精确相等、agent mode 与策略一致、全部观测守恒成立。
9. DeepSeek 局还需 model outcome/fallback 守恒；允许模型暴露为 0，但必须按 v8 原样聚合。任何 malformed、token mismatch、平台错误、非法动作、超时、缺失 audit/tombstone 或非正常结果都使整批立即 invalid。
10. 有效后记录 audit/tombstone bytes+SHA-256 和脱敏聚合，更新 progress，确认 connector 已退出、无活动桌，再进入下一局。

### 批次完成

16 局全部有效后，使用现有 `aggregate_policy_audits()` 按 manifest seed/seat/strategy 和预期 token 做离线聚合：

- 必须 8/8 pairs valid，invalid/incomplete/duplicate/missing 均为 0；
- AB/BA、seat、策略、分数、胜负、模型暴露与 fallback 守恒全部通过；
- 报告不得序列化 token、seed、Bot/match/player、逐局 audit、牌、prompt 或模型内容；
- 只报告描述性胜负、分数差、模型暴露与 fallback，不做显著性、因果或胜率提升结论。

### 判定

16 局及聚合全部通过：

```text
botzone_paired_policy_tokenized_capacity_verified
```

任一局或聚合失败：

```text
botzone_paired_policy_tokenized_capacity_invalid
```

失败时保留已完成局和当前失败证据，但整批不得用于策略比较，也不得继续后续局。成功后才进入更大样本的正式成对评估规划。
