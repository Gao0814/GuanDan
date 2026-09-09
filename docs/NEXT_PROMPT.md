# 给 Coding Codex 的下一任务 Prompt

你负责修正当前工作树中尚未提交的 Botzone decision-trace 实现剩余两项验收缺口，补测试并报告结果。保留现有ACK持久化、fresh输出门槛、随机持久binding和pre-call递归隔离主体；不要回退整个实现，也不要创建Git commit。不要运行真实Botzone、connector进程、Edge、网络、DeepSeek模型或容量评测，不要读取、写入或清理 `D:\VsCodeProject\BotzoneWorkspace`。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 与相关测试。

保持engine/Agent/integration边界。Agent只消费公开observation与原始canonical legal actions，并返回原始合法整数action ID；本任务只修诊断证据及CLI兼容性，不修改策略、规则、协议、fallback、audit或history格式。

固定级牌2、四人、无需进贡、单局是既定范围，不是风险。

## 【当前项目状态】

当前未提交工作树已有完整decision-trace主体：`--decision-trace-file`默认关闭；pending决策只在Header ack后进入confirmed并原子写JSON；重发、重启、replay、重复ack及ack+finished已有测试；trace保存公开observation、canonical legal actions、selected ID/action与低基数source；runner/CLI暴露 `disabled|ok|failed`；v7/v8 audit不变。

上一轮三个反例已经修正：

1. fresh direct CLI会在runner/transport构造前拒绝已有trace文件；
2. session与trace顶层保存独立随机32位binding，同binding及精确前缀才能跨recorder恢复，不同match fail closed；
3. handler在Agent调用前递归隔离证据与Agent输入，selected action从pre-call canonical集合取得。

规划Codex已独立复跑decision-trace/Botzone定向85项、主规则39项、全量704项，均通过；`git diff --check`无whitespace error。但以下两个反例仍成立，所以代码尚未验收、尚未提交：

1. `decision_trace_payload()` 接受observation内 `legal_actions=[{"action_id":999}]`、顶层legal actions为另一份合法pass动作的矛盾输入，返回payload且两份证据不相等。现有handler测试只证明正常构造路径相等，没有把一致性变成持久化校验不变量。
2. direct CLI原 `_history_path()` 会先把相对路径解析为绝对路径，再拒绝仓库内、state内或与audit相同的目标；当前共用 `_diagnostic_path()` 先要求输入本身为absolute。因此从仓库外cwd传入、最终仍解析到仓库外的相对history路径由可用变成configuration error，违反“不改变history兼容语义”。decision trace自身的绝对外部路径要求是新契约，必须继续保留。

## 【本次任务目标】

只修复上述两个缺口：

- decision trace的observation内 `legal_actions` 必须存在、为list，并与顶层 `legal_actions` 在JSON规范化后逐字段、逐顺序完全相等；构建payload和读取持久session都必须fail closed；
- 恢复decision-trace接线前direct CLI的history-only路径语义，同时保持decision trace必须传绝对仓库外路径、已有trace前置拒绝、history/trace冲突拒绝和launcher现有绝对路径门槛。

## 【需要检查的范围】

优先检查：

- `integrations/botzone/session.py`
- `integrations/botzone/__main__.py`
- `tests/test_botzone_decision_trace.py`
- `tests/test_botzone_history.py`
- 现有launcher/connector/runner/session回归

不要修改engine、Agent策略、evaluation、audit schema、history renderer或真实workspace。不要覆盖当前未提交decision-trace主体。

## 【本次任务约束】

- 一致性校验必须在共享payload/parser边界执行，不能只在handler临时断言；observation缺少 `legal_actions`、值为None/非list或与顶层有任一嵌套字段差异时都拒绝。
- 合法payload继续保留pass、逢人配 `declared_cards/carrier_cards/wildcard_count/wildcard_info/display_text` 与table `action_id=None`。
- 可以恢复独立 `_history_path()` 并为decision trace保留专用validator，或采用等价设计；但仅启用history时的既有解析与边界必须保持。
- 从仓库外临时cwd传入相对 `history.txt`、解析结果也在仓库外且不与state/audit冲突时应继续进入runner构造；相对decision trace必须固定拒绝。
- fresh trace已存在时仍必须在runner/transport构造前失败且旧bytes不变。
- pending/ack、binding、重启、finished、旁路失败、三种agent mode source、observability、audit与默认关闭语义不得改变。
- 不新增依赖、不修改`.env`、不创建Git commit。

## 【必须新增的回归测试】

至少覆盖：

1. `decision_trace_payload()` 拒绝observation缺少/None/非list的legal actions；
2. observation与顶层legal actions在action ID、顺序或嵌套 `wildcard_info` 任一处不一致时拒绝；
3. 合法的两份逐字段相等副本继续通过；
4. 将已持久化active session中的observation legal actions单独篡改后，重新加载固定失败；
5. direct CLI从仓库外临时cwd使用相对history路径时，runner builder被调用并收到解析后的仓库外绝对路径；
6. direct CLI相对decision trace仍在runner/transport前拒绝；
7. history与decision trace相同/冲突、已有trace旧bytes不变、launcher既有路径测试继续通过；
8. 现有ACK、binding、Agent mutation、pass/wildcard、三种mode source及隐私测试继续通过。

测试只使用临时目录、patch、假transport和假Agent；不得访问真实workspace、`.env`或网络。

## 【验证要求】

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_botzone_decision_trace tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_launcher tests.test_botzone_history tests.test_botzone_adapter_observation tests.test_botzone_agent_observability -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准】

- 两个规划反例转为稳定回归并通过；
- parser强制两份legal actions完全一致，持久session篡改不能绕过；
- history-only direct CLI旧语义恢复，decision trace的新绝对路径/fresh输出门槛不退化；
- 现有ACK、binding、深隔离、pass/wildcard、三种mode source及隐私边界保持；
- 定向、全量和diff check通过；
- 未运行live、网络、真实模型或容量，未触碰真实workspace，未创建commit。

## 【执行后的报告要求】

最终报告必须包含：

1. 两个反例各自根因；
2. 实际修正设计及修改文件；
3. parser如何保证observation/top-level legal actions一致；
4. history兼容语义与decision-trace新路径门槛如何分离；
5. 新增反例测试与既有ACK/binding/深隔离回归结果；
6. 精确测试命令、项数、结果与 `git diff --check`；
7. 是否访问live、网络、模型、`.env`或真实workspace（预期均为否）；
8. 当前项目范围内是否仍有已知风险。固定级牌2、无贡、单局不得列为风险。
