# GuanDan

一个面向**四人、级牌 `2`、无需进贡的单局掼蛋**规则验证与 AI 决策项目。引擎负责规则真值；AI 在引擎提供的合法动作中选择；Botzone connector 将这条决策链接入本地 AI 长轮询协议。

当前主线不是多局升级或贡还比赛制，也不把本地规则 AI 当作 DeepSeek 路径的替代主线。

## 项目边界

- `engine/`：唯一规则真值，生成 canonical `legal_actions()` 并推进 `step(action_id)`。
- `agents/`：只读取 `observe()` 与完整合法动作，返回原始合法 `action_id`。DeepSeek 是模型路径的主要决策者；RAG 与本地策略信息作为模型前依据，窄范围本地快捷路径除外。
- `integrations/botzone/`：运行在本机的 connector，不是上传到 Botzone 的源码包。它轮询 Botzone 本地 AI 服务，将公开局面交给所选 Agent，再把引擎合法动作转换为平台响应。

合法性、牌型、跟牌压制、逢人配和终局都由引擎裁决；Agent 与 RAG 不生成合法动作，connector 只做协议映射与会话适配。当前 Botzone 适配仅覆盖四人无贡单局的受控子集，不支持贡还阶段。

## Botzone DeepSeek 使用路径

Botzone 主线使用人工创建的四人无贡桌，并在 connector 中**显式选择 `--agent deepseek`**。CLI 的 `--agent` 默认值仍是 `rule`，所以不能省略该选项来启动 DeepSeek。

### 所有者自用：一条命令启动轻量试局

在仓库根目录的 Windows PowerShell 5.1 中运行：

```powershell
.\scripts\run_manual_botzone.cmd
```

启动器使用仓库 `.venv`（若存在）或 `python`，先只读核对 CLI 参数，再对个人 workspace 做零网络配置预检，随后以前台方式启动一个显式 `--agent deepseek` connector。预检成功本身不表示已连接；请等 Botzone 本地 AI 页面显示“已连接”，再由你手动创建四人、级牌 `2`、无需进贡的单局并点击开始。启动器不会操作网页。

个人 connector 沿用此前已进入请求流程的直接调用参数：80 个 cycles、1800 秒墙钟上限、请求超时采用 CLI 默认 30 秒、一次完成后停止；只把 state/audit/history/trace/stream 输出改到个人 workspace。Codex 的固定 workspace 与原执行路径不变。connector 退出时窗口会显示固定 exit code/category，双击启动的窗口会等待按键后关闭；非交互自动调用可使用 `.\scripts\run_manual_botzone.cmd --no-pause`。

`.cmd` 入口以 `-ExecutionPolicy Bypass` 启动一个仅供本次调用的 Windows PowerShell 子进程，并原样返回脚本退出码；不会修改 LocalMachine、CurrentUser 或持久策略。若企业组策略仍禁止该进程运行，应停止并联系管理员，不要尝试全局放宽执行策略。

预检与真实运行使用同一 Python 解释器、仓库工作目录和继承环境；旧成功进程的解释器及环境没有可比记录，因此这里只确认当前启动链一致，不声称两次运行环境完全相同。

个人运行证据固定保存在仓库外 `D:\VsCodeProject\GuanDanManualWorkspace`，与 Codex 正式 workspace `D:\VsCodeProject\BotzoneWorkspace` 分开。下次启动时，只有个人根路径、归属标记、白名单目录/文件类型和 connector 状态全部通过检查，且零网络配置预检成功，启动器才会把上次个人目录移入 Windows 回收站并重建；任何未知对象或检查/回收失败都会停止并保留旧内容。**如果本次发现问题或希望 Codex 复查，先不要再次运行启动器**，否则它会按规则回收上一轮个人目录。

该检查只能发现本机可归属的 connector；Botzone 本地 AI 连接端点可能被另一台主机同时使用，跨主机并行无法由本机进程检查保证。不要让个人试局与 Codex connector 同时连接同一个端点。个人启动器把 `DEEPSEEK_MAX_RETRIES=0` 只设到本次 connector 子进程，退出后恢复；URL 与 DeepSeek 凭据继续走现有私密配置，不写入命令行示例或日志。

### Codex 监督运行：固定审计 workspace

以下是与个人启动器分离的正式/Codex 监督流程；不要把两种 workspace 混用。

#### 1. 准备固定 workspace 与本地配置

运行状态与证据只放在仓库外固定目录 `D:\VsCodeProject\BotzoneWorkspace`，不要新建其他 `Botzone*` 顶层目录。`state`、`audit`、`streams` 是该 workspace 下允许使用的子目录：

```powershell
$workspace = 'D:\VsCodeProject\BotzoneWorkspace'
New-Item -ItemType Directory -Force `
  "$workspace\state", "$workspace\audit", "$workspace\streams" | Out-Null
$env:BOTZONE_STATE_DIR = "$workspace\state"
```

正式 live 前，按 Skill 确认 workspace 根和这三个子目录都是普通目录、没有未知内容，并确认没有仍在运行的项目 connector；不符合时先停止，不要靠 `-Force` 或换目录绕过检查。

在 Botzone“本地 AI 配置”中配置连接信息，并按本地安全方式向当前进程提供 `BOTZONE_LOCAL_AI_URL`；不要把平台 URL 或连接密钥写入仓库、命令示例或共享记录。DeepSeek 凭据和模型设置通过项目现有 `config.py` 配置路径提供；不要手工复制或输出密钥。

每次运行前，确认本轮选用的 audit、history、trace、stdout 和 stderr 路径均不存在。当前 CLI 会原子替换已有 audit/history 文件；decision trace 若已存在则拒绝启动。若固定 workspace 留有上一轮证据，不要覆盖或自行清空；先结束当前工作，再按 `botzone-workspace-recycle` Skill 对已审计证据单独处理。

#### 2. 做零网络配置预检——它不表示已连接

```powershell
python -m integrations.botzone `
  --preflight-only `
  --agent deepseek `
  --state-dir "$workspace\state"
```

预检读取 Botzone URL/state 配置，检查 state 目录并验证 DeepSeek Agent 组合；成功输出 `preflight_ready`。此模式在创建 Botzone HTTP transport 前返回，不发起 Botzone 长轮询或 DeepSeek 请求，**`preflight_ready` 不是“已连接”证明**。

#### 3. 前台启动真实 connector，并等到页面确认连接

先确认下面五个目标证据不存在：`audit\completion-audit.json`、`history.txt`、`decision-trace.json`、`streams\stdout.txt`、`streams\stderr.txt`。正式单局还应遵守 `botzone-manual-live` Skill 的 workspace、预算、监测和证据门槛。以下示例不含 URL、密钥或固定 seed；它只启动 connector，建桌和点击开始由项目所有者在页面手动完成。

```powershell
$previousRetries = $env:DEEPSEEK_MAX_RETRIES
$env:DEEPSEEK_MAX_RETRIES = '0'
$runToken = [guid]::NewGuid().ToString('N').ToLowerInvariant()
try {
  python -m integrations.botzone `
    --agent deepseek `
    --state-dir "$workspace\state" `
    --timeout-seconds 30 `
    --max-cycles 100 `
    --max-wall-seconds 600 `
    --stop-after-finished 1 `
    --audit-file "$workspace\audit\completion-audit.json" `
    --history-file "$workspace\history.txt" `
    --decision-trace-file "$workspace\decision-trace.json" `
    --run-token $runToken `
    1> "$workspace\streams\stdout.txt" `
    2> "$workspace\streams\stderr.txt"
} finally {
  if ($null -eq $previousRetries) {
    Remove-Item Env:DEEPSEEK_MAX_RETRIES -ErrorAction SilentlyContinue
  } else {
    $env:DEEPSEEK_MAX_RETRIES = $previousRetries
  }
  Remove-Variable runToken, previousRetries -ErrorAction SilentlyContinue
}
```

这里将 DeepSeek 重试数仅对该 connector 进程设为 `0`，退出后恢复原 PowerShell 环境。保持前台进程运行；进程存活或长轮询等待本身不等于已连接。看到 Botzone 页面明确显示“已连接”后，再提供本次建桌配置。桌面选择掼蛋、四人、本地 AI、无需进贡；由项目所有者手动创建并确认配置，随后手动点击开始一次。

`--preflight-only` 与真实运行不能混淆：实际长轮询命令**不带**该开关。正常结束时 CLI 会输出低基数 `connector_finished` 汇总；退出码 `0` 也可能表示预检成功，因此应结合是否启动了真实 connector 及 audit 状态判断，不把预检退出码当作对局完成证据。

`--history-file` 与 `--decision-trace-file` 是显式 opt-in 的诊断文件，可能包含公开观察、出牌及本家手牌等局内信息；audit 可能包含 run token。所有这些都按私有运行证据处理，只保存在固定 workspace，不放入 Git、普通日志或共享聊天。audit 为聚合证据。结束后按 Skill 与当前 schema 审核 connector、ACK trace 和 audit 守恒；平台结局有效性与决策证据有效性应分别判断。单局结果不证明策略收益或胜率。

## 本地开发与辅助调试

需要 Python 3.11 和 `requirements.txt` 中的依赖。先运行规则回归或全量测试：

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -q
```

下面是**本地四 AI 调试辅助入口**，不是 Botzone connector：

```powershell
# CLI 默认 --agent rule；可选 --seed 参数可用于本地复现
python -m cli.run_4ai_debug --max-steps 5000

# 可选的本地 DeepSeek 调试；未被本地快捷路径处理的决策会调用模型服务
python -m cli.run_4ai_debug --agent deepseek --max-steps 10
```

真实 DeepSeek 调试会向配置的模型服务发送决策上下文；先确认本地凭据配置和数据外发边界，不要共享 prompt、模型响应或密钥。Botzone 操作不是该 CLI 的延伸，应使用上面的 connector 流程。

## 常用测试与代码导航

```powershell
# 引擎主回归
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q

# Botzone connector 离线回归
python -m unittest `
  tests.test_botzone_cards `
  tests.test_botzone_protocol `
  tests.test_botzone_session `
  tests.test_botzone_connector `
  tests.test_botzone_rule_agent_e2e `
  tests.test_botzone_runtime_config `
  tests.test_botzone_live_preflight -q
```

```text
engine/                  单局规则真值
agents/                  RuleBased、DeepSeek、RAG 与策略投影
rag/                     规则知识与经验语料
cli/                     本地四 AI 调试入口
integrations/botzone/    本机 connector、协议与会话适配
tests/                   unittest 回归
docs/                    规格、不变量、边界与项目计划
```

理解实现时可从 `docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`engine/game.py`、`agents/deepseek_ai.py` 和 `integrations/botzone/__main__.py` 开始。
