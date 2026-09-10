# 给 Coding Codex 的下一任务 Prompt

执行一次人工 Botzone 单局 `deepseek` 决策证据采样。不要修改仓库文件；本任务不是容量实验，也不负责赛后算法修改。

## 【开始前】

1. 阅读并遵守 `AGENTS.md`。
2. 完整读取并执行项目 Skill：`.agents/skills/botzone-manual-live/SKILL.md`。
3. 阅读 `docs/CLEAN_HANDOFF.md`，检查当前 Git 状态和实际 workspace。

## 【当前状态】

- acknowledged decision trace实现已提交为 `045fb75`，规划复审结果为Botzone定向88项、主规则39项、全量707项通过。
- seed `47002` evidence已审计并回收。预期 `D:\VsCodeProject` 下唯一 `Botzone*` 顶层目录为 `BotzoneWorkspace`，其递归内容精确为三个空的普通非链接目录：`audit/`、`state/`、`streams/`；无项目connector，Git clean。开始前必须自行复核。

## 【本次输入与目标】

- Agent：`deepseek`
- seed：`47003`
- 本家：玩家1 / seat 0
- 当前级牌：`2`
- 需要进贡：`否`
- `timeout-seconds=120`
- `max-cycles=100`
- `max-wall-seconds=3600`
- `stop-after-finished=1`
- 新的随机32位小写十六进制run token，不得输出

目标artifact：

```text
D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json
D:\VsCodeProject\BotzoneWorkspace\history.txt
D:\VsCodeProject\BotzoneWorkspace\decision-trace.json
D:\VsCodeProject\BotzoneWorkspace\state\<唯一session或finished tombstone>.json
D:\VsCodeProject\BotzoneWorkspace\streams\stdout.txt
D:\VsCodeProject\BotzoneWorkspace\streams\stderr.txt
```

使用项目 `.venv\Scripts\python.exe` 完成一次零网络 `deepseek` preflight，再通过 `integrations.botzone.live_launcher` 启动唯一持续connector。严格遵循 Skill 的连接、人工建桌、配置核对、开始和监测顺序：页面确认“已连接”后才向项目所有者发送seed `47003`及配置；seed从该消息起视为已使用。

## 【本次特殊约束】

- 最多一个connector、一个目标桌和一局；不得为追求某个source、守卫触发、胜负或更干净结果重开。
- 对局开始后仓库与workspace evidence冻结；不得清理或现场修代码。发现代码问题时保留证据并报告。
- 页面只读监督不可用时，继续等待并接受项目所有者明确确认，不得把监督失败当作live失败；明确看到配置不匹配时必须等待修正。
- 非致命 `http_error` 若未阻止完成或破坏delivery/ack守恒，只记为传输观察，不自动作废对局。
- 不读取或输出 `.env`、URL、密钥、token、Header、Cookie、本家手牌、完整history/trace、observation/legal actions、prompt、模型响应或reasoning。

## 【完成与报告】

正常完成且history/trace/audit/state守恒时使用：

```text
botzone_deepseek_decision_trace_sample_completed
```

按 Skill 完成低敏验证并保留全部evidence。最终报告：实际阶段和交互顺序；connector/cycle/request/response/Header/finished/transport计数；model outcome、fallback和source聚合；history/trace状态及decision数量守恒；各artifact相对路径、bytes和SHA-256；Git前后状态、残留connector和第二桌计数；当前范围内真实剩余风险。

如果已开始但未完成，保留现场、使用准确低敏边界并停止，不重试。若页面一直未连接且seed未提示，保持等待项目所有者指示，不得声称seed已消耗。完成后提交业务修改的通用规则不适用于本任务，因为本任务禁止仓库修改。
