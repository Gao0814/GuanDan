# 给 Coding Codex 的下一任务 Prompt

你负责本次代码实现、测试与结果报告。本任务只做离线实现：为 Botzone connector 增加显式 opt-in、仓库外、只记录成功 Header acknowledgement 后本家决策的结构化证据文件。不要运行真实 Botzone、connector、Edge、网络、DeepSeek 模型或容量评测，不要读取、写入或清理 `D:\VsCodeProject\BotzoneWorkspace`。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 与相关实现/测试。

保持 engine/Agent/integration 边界：Agent 只消费公开 observation 和原始 canonical legal actions，并返回其中的原始整数 `action_id`；Botzone 实体 `[action, claim]` 仍只能由 adapter provenance 生成。本任务是诊断证据，不得改变动作选择、规则真值、请求/响应协议或 fallback 语义。

当前固定级牌 `2`、四人、无需进贡、单局是既定项目范围，不是风险或未完成项。

## 【当前项目状态】

最新算法检查点为 `295b9b5`，规划文档检查点为 `2c773fe`，任务开始时仍须以实际 Git 状态为准。当前全量回归基线为 689 项通过。

seed `47002` 的只读复盘已结束：16次本家决策中14次可按公开语义重建，9个pass点均只有pass合法；两个可精确比较的自由出牌点没有严格更优替代。第1、6次因现有可读history未保存足以唯一还原的canonical声明/载体细节，不能形成新策略缺陷。结论是现有evidence不足以支持下一项算法修改。

代码在 `NoTributeRuleBasedHandler` 决策时已经同时拥有：

- 传给Agent的完整公开 observation；
- 当次原始 canonical legal actions；
- 经合法性验证的最终原始 selected action ID及对应action；
- 最终低基数 decision source。

但现有pending/ack持久化只保存 `PlayEffect` 的carrier/claim；`history.txt`只保存可读公开牌谱，无法恢复每一步当时的完整legal action集合。`agents/decision_trace.py` 有一个未接入runtime的 `DecisionRecord`，可评估复用，但不得因此输出其中可能含有的自由文本notes、模型prompt/reasoning或其他非必要字段。

## 【本次任务目标】

新增一个精确参数：

```text
--decision-trace-file <absolute external path>
```

默认不传时完全关闭。传入时，为单个match原子维护一个确定性JSON文件，目标用途是让下一次单局结束后可精确重放每个**已成功ack的本家决策输入与输出**。

每条确认记录至少包含：

1. 从1开始、按ack顺序稳定递增的本家决策序号；
2. 当时传给Agent的完整公开 observation；
3. 当时的原始 canonical legal actions，顺序和字段不变；
4. 最终 selected action ID；
5. 从同一原始legal actions中按ID唯一取得的 selected action完整公开字典；
6. 最终低基数 decision source。

顶层必须有固定schema/version，并明确作用域是“acknowledged local decisions only”。不得把该文件描述为完整裁判牌谱或全部玩家决策。

## 【需要检查的范围】

优先检查：

- `integrations/botzone/play_adapter.py`
- `integrations/botzone/session.py`
- `integrations/botzone/connector.py`
- `integrations/botzone/history.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `integrations/botzone/live_launcher.py`
- `integrations/botzone/agent_observability.py`
- `agents/decision_trace.py`
- 对应 session、connector、runner、launcher、history、adapter 测试

先确认handler生成决策、pending response/effect持久化、transport ack、finished tombstone与recorder更新的真实顺序，再选择最小实现。不要假设问题一定要通过某一个类或字段解决；但进程重启后未ack决策仍必须能够在后来ack时正确提交，不能只依赖易丢失的进程内缓存。

## 【本次任务约束】

- 只做与该证据文件直接相关的最小修改，不做策略优化、规则重构、transport修复或audit升级。
- 文件必须显式opt-in；默认 CLI、runner、launcher 和现有history行为逐字节兼容。
- 只允许记录成功Header ack后的决策。handler已返回、pending已生成但尚未ack时，不得把该动作写成已发生决策。
- transport timeout/failure、pending重发、envelope/direct replay、重复ack和进程重启不得导致重复记录。
- ack与qualified finished出现在同一poll时，必须在tombstone前保留最后一条已确认决策。
- recorder是旁路诊断：写入失败不得改变response delivery、ack、扣牌、session、finished或Agent行为。失败后暴露固定低敏 `disabled / ok / failed` 状态。
- 单个文件只绑定一个match；第二match必须fail closed并保留首局已有文件，不覆盖、不拼接。
- 使用UTF-8/LF、确定性字段/列表顺序和原子替换；替换失败清理临时文件并保留最后一份有效内容。
- 输出只能包含上述公开决策字段与固定低敏元数据。不得包含match ID、run token、连接URL、Header、Cookie、API key、模型prompt/response/reasoning、异常正文或自由文本notes。
- observation可含本家完整公开手牌，因此目标文件只能位于仓库外；不得进入v8 audit、stdout、stderr、普通日志或仓库文件。
- 新路径不得位于仓库内、state目录或streams目录，不得等于或嵌套冲突于audit/history/其他输出路径。launcher需做路径唯一性与输出预存在检查。
- 不新增依赖，不修改`.env`，不覆盖无关未提交改动，不创建Git commit。

## 【重要不变量】

- `selected_action_id` 必须是非bool整数，并存在于该条记录保存的原始legal actions；`selected_action` 必须与该ID对应的原始字典完全一致。
- table action继续使用canonical `action_id=None`；不得重新引入整数table identity、history step ID或人为sentinel。
- pending response/effect只在transport ack后提交；重发、重启或重复ack不得重复扣牌或重复记录。
- `rule`、`deepseek`、`conditional_pressure_pass` 的动作选择及decision source守恒保持不变。
- DeepSeek的 `danger_opponent_block`、`teammate_control_block`、`short_endgame_plan` 优先级和fallback语义不得改变。
- v7/v8 audit schema/version与现有human-readable `history.txt` 格式不得改变。
- active session的兼容读取和v4 finished tombstone必须保持；不要让新增诊断字段破坏旧state/replay恢复。

## 【验证要求】

至少新增或调整合成测试覆盖：

1. 默认关闭，不创建文件，既有输出和summary兼容；
2. handler完成、pending存在但未ack时文件不包含该决策；
3. 成功Header ack后恰好出现一次完整observation/legal actions/selected ID/action/source；
4. timeout或transport failure后重发，再ack，只记录一次；
5. 保存pending后重建store/connector模拟进程重启，再ack，记录仍完整且只出现一次；
6. envelope/direct replay、重复request或公开history replay不重复；
7. ack后立即同poll收到qualified finished，最后决策仍存在；
8. pass与含逢人配声明的动作均保持原始canonical字段；
9. 第二match拒绝覆盖/拼接首局；
10. 原子替换失败后状态为failed、临时文件清理、最后有效文件保留，connector交付不受影响；
11. CLI/launcher接受精确参数，拒绝相对路径、仓库内路径、state/streams嵌套、与audit/history/stream重复及预存在输出；
12. 三种agent mode的source记录与现有observability计数不漂移；
13. 不序列化match/token/URL/Header/model自由文本等禁用字段。

先运行新增/相关定向测试，再运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_launcher tests.test_botzone_history tests.test_botzone_adapter_observation tests.test_botzone_agent_observability -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

如果新增独立测试模块，把它加入第一条定向命令。测试只能使用临时目录和假transport/Agent，不得访问真实workspace、网络或`.env`。

## 【完成标准】

- `--decision-trace-file` 形成默认关闭、仓库外、单match、原子且可恢复的结构化JSON证据；
- 每条记录仅在ack后出现，并完整保留当次公开observation、原始canonical legal actions、原始selected ID/action和低基数source；
- 重发、重启、replay、重复ack与finished同poll均不丢失、不重复；
- recorder失败不影响connector事务；默认行为、Agent选择、history和v7/v8 audit不变；
- 相关测试与全量测试通过，未引入超出本任务范围的重构；
- 未运行live、Botzone、Edge、网络、真实模型或容量，未触碰真实workspace，未创建Git commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 现有证据缺口及选择的ack持久化设计；
2. 实际修改内容和文件；
3. JSON的固定字段、隐私边界与单match策略；
4. pending/ack、重发、重启、finished同poll的行为；
5. 为什么不会改变动作选择、audit或现有history；
6. 运行的精确测试命令、项数与结果；
7. `git diff --check` 结果；
8. 是否访问live、网络、模型、`.env`或真实workspace（预期均为否）；
9. 当前项目范围内是否仍有已知风险。固定级牌2、无贡、单局不得列为风险。
