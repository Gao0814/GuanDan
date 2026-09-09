# 给 Coding Codex 的下一任务 Prompt

你负责修正当前工作树中尚未提交的 Botzone decision-trace 实现、补测试并报告结果。保留已经成立的ack持久化与旁路写入主体，不要回退整个实现，也不要创建Git commit。不要运行真实Botzone、connector进程、Edge、网络、DeepSeek模型或容量评测，不要读取、写入或清理 `D:\VsCodeProject\BotzoneWorkspace`。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 与相关测试。

保持engine/Agent/integration边界。Agent只消费公开observation与原始canonical legal actions，并返回原始合法整数action ID；Botzone实体action/claim仍只由adapter provenance产生。本任务只修诊断证据，不修改策略、规则、协议、fallback或audit。

固定级牌2、四人、无需进贡、单局是既定范围，不是风险。

## 【当前项目状态】

任务开始时，代码工作树中已有未提交的decision-trace实现，主要包括：

- 新 `integrations/botzone/decision_trace.py` 与对应测试；
- session中的pending/confirmed decision payload；
- handler、connector、runner、CLI、launcher接线；
- `--decision-trace-file`、原子JSON与 `disabled|ok|failed` 状态。

执行方报告的78项定向与697项全量测试，规划Codex均已独立复跑通过；`git diff --check`也通过。但以下三个额外反例实际成立，因此当前实现尚未通过验收、尚未提交：

1. **fresh direct CLI没有前置拒绝既有trace文件。** 在临时目录预创建绝对 `trace.json`，patch `build_foreground_runner` 后调用带 `--decision-trace-file` 的CLI，builder仍被调用；返回2只是后续合成异常造成的。
2. **single-match绑定不能跨recorder实例证明。** match A写入后重建 `ConnectorDecisionTrace`，再用决策内容完全相同的match B更新，状态仍为 `ok`，文件未被判冲突。当前仅比较decision前缀，不能证明同一match恢复。
3. **所谓原始canonical快照可被Agent污染。** handler只浅复制action字典；合成Agent在 `select_action()` 中修改非选中action的嵌套 `wildcard_info` 后，trace不再等于调用前 `project_decision()` 结果，且未标记failed。

## 【本次任务目标】

只修复以上三个实证缺口，并补齐上一任务遗漏的两类验收测试：三种agent mode的source进入trace且不改变observability；pass和含逢人配声明动作的canonical字段逐字段保留。

修正后必须满足：

- fresh CLI/launcher使用已存在的decision-trace输出时，在runner/transport构造前固定失败，且旧文件逐字节不变；不要顺带改变现有history文件兼容语义；
- recorder实例重建后，只有可持久证明为同一trace会话的已有文件才能作为前缀恢复；不同match即使decision内容完全相同也必须failed并保留原文件；
- trace中的observation/legal actions是Agent调用前的深隔离快照，Agent对传入observation、legal actions及任意嵌套list/dict的修改都不能影响证据；selected action也必须从该份调用前canonical集合按最终合法ID取得。

## 【实现边界】

允许为single-match恢复增加一个独立、低敏、随机且持久的trace绑定ID，例如固定32位小写十六进制值，但必须满足：

- 不由match ID、run token、URL、Header或牌面派生；
- 与active session一起持久化，并进入trace顶层用于恢复一致性；
- 不替代现有run provenance，不进入audit、stdout、stderr或网络；
- 老v3/v4 active session/tombstone兼容读取不破坏；
- 第二match获得不同绑定，不能只凭相同decision前缀冒充恢复。

如果选择其他设计，也必须用测试证明同match恢复与不同match拒绝，不得把match ID、run token或其可逆形式写入trace。

CLI的fresh输出门槛与内部recorder恢复要区分：普通新CLI/launcher调用继续拒绝预存在输出；内部合成恢复只有在持久绑定一致且已有decisions为当前confirmed decisions精确前缀时才允许。不要为了恢复而普遍允许任意既有文件。

## 【需要检查的范围】

优先检查当前未提交差异及：

- `integrations/botzone/play_adapter.py`
- `integrations/botzone/session.py`
- `integrations/botzone/decision_trace.py`
- `integrations/botzone/connector.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `integrations/botzone/live_launcher.py`
- `integrations/botzone/agent_observability.py`
- 新增及现有session/connector/runner/launcher/history/adapter/observability测试

不要修改engine、默认Agent策略、evaluation或真实workspace。不要覆盖工作树中当前decision-trace主体。

## 【本次任务约束】

- 对Agent输入和trace保留值使用真正的递归隔离；仅复制外层dict不够。
- trace保留的observation中 `legal_actions` 必须与顶层保存的原始legal actions逐字段一致。
- Agent即使删除字段、追加wildcard_info、修改display text或改写observation历史，也不能污染trace或adapter provenance。
- final selected ID仍必须经过现有合法性检查；trace selected action必须来自隔离前的原始canonical集合。
- pending未ack不落盘；timeout/failure、重发、重启、replay、重复ack不重复；ack与finished同poll仍保留最后决策。
- recorder失败不影响response、ack、扣牌、session、finished、history或audit。
- JSON仍不得含match ID、run token、URL、Header、Cookie、key、prompt、模型response/reasoning、notes或异常正文。
- table action继续为canonical `action_id=None`；不得重引入整数table identity。
- v7/v8 audit schema、现有history格式、三种agent mode动作与source守恒不得改变。
- 不新增依赖、不修改`.env`、不创建Git commit。

## 【必须新增的回归测试】

至少覆盖：

1. direct CLI预存在decision-trace时，runner builder未调用、固定configuration失败、旧bytes不变；
2. launcher预存在decision-trace继续前置拒绝；
3. match A写入后重建recorder，同一持久trace绑定和精确前缀可恢复且不重复；
4. 重建recorder后match B即使所有decision内容与A相同，也因绑定不同failed，A文件不变；
5. 缺失、畸形、bool或不匹配的trace绑定fail closed；
6. 合成Agent同时修改传入observation、legal actions及嵌套 `wildcard_info`，输出仍精确等于调用前公开projection；
7. trace observation内的legal actions与trace顶层legal actions相等；
8. 选中pass时selected ID/action精确来自原始集合；
9. 选中含逢人配声明动作时declared/carrier/wildcard_info/display字段逐项保持；
10. `rule`、`deepseek`、`conditional_pressure_pass` 至少各有一个trace source断言，并同时验证现有observability计数不漂移；
11. 既有pending/ack、restart、finished同poll、第二match、atomic failure和隐私测试继续通过；
12. 旧session/tombstone兼容回归继续通过。

测试只使用临时目录、假transport和假Agent。不得访问真实workspace、`.env`或网络。

## 【验证要求】

先运行新增decision-trace与三个反例测试，再运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_botzone_decision_trace tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_launcher tests.test_botzone_history tests.test_botzone_adapter_observation tests.test_botzone_agent_observability -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准】

- 三个规划反例全部转为稳定回归并通过；
- fresh输出前置失败与内部同match恢复边界不混淆；
- 持久绑定能区分不同match，且不泄露match/run身份；
- Agent无法污染调用前canonical证据；
- pass、wildcard与三种mode source证据完整，observability不漂移；
- 原ack、重发、重启、finished、旁路失败与隐私边界保持；
- 定向、全量和diff check通过；
- 未运行live、网络、真实模型或容量，未触碰真实workspace，未创建commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 三个反例各自根因；
2. 实际修正设计及修改文件；
3. fresh输出拒绝与同match恢复如何区分；
4. trace绑定为何不泄露match/run身份；
5. pre-call深隔离如何保证canonical证据不受Agent修改；
6. pass、wildcard、三种mode source测试结果；
7. 精确测试命令、项数、结果与 `git diff --check`；
8. 是否访问live、网络、模型、`.env`或真实workspace（预期均为否）；
9. 当前项目范围内是否仍有已知风险。固定级牌2、无贡、单局不得列为风险。
