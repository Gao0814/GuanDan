# GuanDan

一个用于单局掼蛋规则验证与 AI 决策实验的 Python 项目。项目提供三条明确分离的运行路径：

1. `engine/`：单局掼蛋的规则真值。
2. `agents/`：只能从引擎公开的 observation 和合法动作中选择 `action_id` 的 AI 决策层。
3. `integrations/botzone/`：把 Botzone 本地 AI 长轮询协议适配到本项目，供真实平台测试使用。

当前推荐先用本地 CLI 验证规则与策略，再通过 Botzone 本地 AI connector 做固定级牌 2、无需进贡的单局测试。引擎保留级牌/逢人配规则接口，但当前算法主线不做 13 级牌泛化、多局升级或贡还流程。

## 1. 快速开始

要求：Python 3.11 和本项目依赖。

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -q
python -m cli.run_4ai_debug --seed 7 --max-steps 5000
```

最后一条命令会启动四个默认 `RuleBasedAI` 完成一局本地模拟。固定 `--seed` 可复现发牌与对局。

## 2. 如何理解项目

### 规则引擎：`engine/`

规则引擎是唯一规则真值，负责：

- 牌、牌型、通配牌和炸弹层级；
- 合法动作生成与压制判断；
- 当前行动玩家、接风、名次、终局和胜负推进；
- 四个公开接口：`reset()`、`observe()`、`legal_actions()`、`step(action_id)`。

不要让 AI 或 Botzone 适配层自行裁决牌型或合法性。所有实际执行都应回到引擎给出的合法动作集合。

### AI 决策层：`agents/`

AI 层只读取公开数据：

```python
observation = game.observe()
legal_actions = game.legal_actions()
action_id = agent.select_action(observation, legal_actions)
game.step(action_id)
```

其中 `legal_actions()` 返回 canonical action；动作含 `action_id`、声明牌型、声明牌、真实承载牌、通配信息和展示文本。AI 只能返回已有 `action_id`，不能构造新动作，也不能读取 `GameState`、`PlayerState` 或 `Action` 等内部对象。

主要模块：

- `agents/rule_based_ai.py`：默认、可复现的本地规则 AI。
- `agents/deepseek_ai.py`：可选的 DeepSeek 决策链，先执行本地短路和开局策略，再按需调用模型。
- `agents/opening_strategy.py`：早期首出本地公式化策略。
- `agents/hand_evaluator.py`、`agents/card_tracker.py`：公开手牌/历史的辅助评分与记牌。
- `agents/rag_advisor.py`：规则和经验上下文，仅供模型参考，不参与合法性裁决。

### 本地调试入口：`cli/`

```powershell
# 默认 RuleBasedAI 对局
python -m cli.run_4ai_debug --seed 42 --max-steps 5000

# DeepSeek 路径的小步调试；需要本地配置 DeepSeek 环境变量
python -m cli.run_4ai_debug --agent deepseek --seed 7 --max-steps 10

# 显示 DeepSeek 玩家 1 的决策信息
python -m cli.run_4ai_debug --agent deepseek --show-thinking --seed 7 --max-steps 10
```

`--agent rule` 是默认值。DeepSeek 仅在本地短路未命中时才会调用 RAG/模型；不要把真实 API 密钥提交到仓库。

### Botzone 集成层：`integrations/botzone/`

该层不是规则引擎，也不是上传到 Botzone 的源码包。它是在你的电脑上运行的 connector：

```text
Botzone 本地 AI 网关
       ^  HTTPS GET 长轮询；后续请求 Header 回传 response
       |
integrations/botzone connector
       |
Botzone 请求 -> 公开局面投影 -> agent.select_action(...) -> action_id
       |
原始合法动作 -> Botzone [action, claim]
```

connector 只保存每个对局所需的本地会话状态；它不向 AI 暴露 Botzone 的内部数据。`play` 动作仍由规则投影产生合法动作，再将选中的原始动作转换回 Botzone 的真实承载牌 `action` 与声明牌 `claim`。

## 3. Botzone connector：当前支持范围

连接器目前面向 **Botzone 手动创建的四人、无贡对局**：

- 支持 `deal` 和 `play`；
- 支持 Botzone 的 `0..107` 实体牌 ID、动作/声明牌回写、历史合并、会话持久化和重启后的待发送动作恢复；
- 默认调用 `RuleBasedAI`；可显式选择 `--agent deepseek`；
- `tribute`、`return` 和其他不受支持阶段会 fail-closed，connector 会停止而不是伪造响应；
- 当前无贡适配是规则投影的受控子集，不应宣称为完整的 Botzone 多局贡还规则实现。

因此，在 Botzone 创建游戏桌时必须手动选择：**掼蛋、四人、本地 AI、需要进贡：否**。不要用贡还局测试当前 connector。

## 4. 启动 Botzone connector

### 4.1 先在 Botzone 配置本地 AI

1. 打开 Botzone 的“本地 AI 配置”。
2. 轮换并保存一个新的连接密钥。不要复用截图、聊天记录或提交历史中出现过的密钥。
3. 点击提交后复制平台提供的本地 AI URL。
4. 不要把 URL、密钥写入源码、README、测试、Git 或共享的 `.env`。

本地 AI 是你的电脑主动发起 HTTPS GET 连接，因此通常不需要给本机开放公网端口。

### 4.2 为 connector 准备两个仓库外目录

连接器要求会话状态目录在仓库外。建议同时准备独立 audit 目录：

```powershell
New-Item -ItemType Directory -Force D:\BotzoneState\GuanDan | Out-Null
New-Item -ItemType Directory -Force D:\BotzoneAudit | Out-Null
```

- `D:\BotzoneState\GuanDan`：持久化每个未结束对局的最小会话状态。不要放在本仓库、`logs/` 或 Git 管理目录中。
- `D:\BotzoneAudit`：保存一次运行的汇总审计文件；不保存完整手牌、原始请求或连接 URL。

### 4.3 仅在当前 PowerShell 会话设置连接信息

将下面的占位符替换为 Botzone 页面给出的 URL。不要将真实 URL 粘贴到代码或文档中。

```powershell
$env:BOTZONE_LOCAL_AI_URL = 'https://<botzone-local-ai-url>'
$env:BOTZONE_STATE_DIR = 'D:\BotzoneState\GuanDan'
```

也可以使用命令行参数 `--url` 和 `--state-dir`。显式参数优先于环境变量。

### 4.4 先做零联网预检

预检只验证 URL 形状、state 目录可写性和 agent 组合，**不会发起 GET、不会连接 Botzone、不会调用 DeepSeek**：

```powershell
python -m integrations.botzone --preflight-only --agent rule
```

成功时输出：

```text
preflight_ready
```

常见失败：

- `preflight_runtime_config_missing`：未设置 URL 或 state 目录。
- `preflight_runtime_config_url_invalid`：URL 不是 HTTPS 或格式不合法。
- `preflight_state_directory_invalid`：state 目录位于仓库内，或路径不合规。
- `preflight_state_operation_failed`：目录不可创建、不可写或文件系统操作失败。

修复预检错误后再继续；不要在预检未通过时创建 Botzone 对局。

### 4.5 前台运行 RuleBased connector

先启动 connector，再在 Botzone 手动创建“需要进贡：否”的测试桌：

```powershell
python -m integrations.botzone `
  --agent rule `
  --timeout-seconds 30 `
  --max-cycles 100 `
  --max-wall-seconds 600 `
  --stop-after-finished 1 `
  --audit-file 'D:\BotzoneAudit\guandan-rule-smoke.json'
```

运行期间保持该 PowerShell 窗口打开。connector 在到达一局合格终局、循环上限、时长上限、协议错误或连续传输失败上限时退出。按 `Ctrl+C` 可主动停止。

成功终止时会输出类似：

```text
connector_finished cycles=<n> finished=<n> exit=0
```

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 预检通过，或达到要求的合格终局 |
| `2` | 配置错误 |
| `4` | 传输失败次数达到上限 |
| `5` | 协议/不支持阶段错误 |
| `6` | 对局未在 cycle 或时长上限内完成 |
| `130` | 被 Ctrl+C 中断 |

### 4.6 可选：DeepSeek connector

先用 `rule` 完成稳定的无贡对局，再考虑：

```powershell
python -m integrations.botzone --preflight-only --agent deepseek
```

DeepSeek 路径仍遵循项目的本地短路、RAG、原始动作校验和规则 AI fallback。它需要有效的本地 DeepSeek 配置，且会将本家公开决策上下文发送给模型服务；使用前确认你接受这一外发行为及模型延迟。不要把真实 Botzone URL 或 DeepSeek 密钥写进命令历史、脚本或仓库。

## 5. 常用测试

```powershell
# 全量回归
python -m unittest discover -q

# 引擎主回归
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q

# Botzone connector 的离线回归，不会使用真实 URL
python -m unittest `
  tests.test_botzone_cards `
  tests.test_botzone_protocol `
  tests.test_botzone_session `
  tests.test_botzone_connector `
  tests.test_botzone_rule_agent_e2e `
  tests.test_botzone_runtime_config `
  tests.test_botzone_live_preflight -q
```

## 6. 目录导览

```text
engine/                  单局规则真值
agents/                  RuleBased、DeepSeek、评分、记牌、RAG、开局策略
rag/                     中文规则库和经验库
cli/                     本地四 AI 调试命令
integrations/botzone/    本机 connector、协议、会话、动作适配、运行器
tests/                   unittest 回归测试
docs/                    规则规格、边界、不变量、测试与集成计划
```

推荐阅读顺序：

1. `docs/SPEC.md`：项目规则与公开接口范围。
2. `docs/CODING_BOUNDARY.md`、`docs/INVARIANTS.md`：不能突破的架构和规则边界。
3. `engine/game.py`、`engine/rules.py`：公开接口与合法动作来源。
4. `agents/base.py`、`agents/rule_based_ai.py`：AI 如何只选择 action_id。
5. `integrations/botzone/__main__.py`、`integrations/botzone/runner.py`、`integrations/botzone/play_adapter.py`：connector 如何运行并做协议适配。
6. `docs/BOTZONE_INTEGRATION_PLAN.md`：Botzone 集成范围、已验证内容和剩余限制。

## 7. 开发边界

- 不修改 `engine/` 的 `observe()`、`legal_actions()`、`step(action_id)` 公开契约。
- AI、RAG、剪枝与 connector 都不能生成或裁决合法动作。
- 最终执行的 `action_id` 必须来自原始 `legal_actions()`。
- 不提交 `.env`、Botzone 本地 AI URL、连接密钥、DeepSeek 密钥、会话 state 或运行审计文件。
- 不要把 `integrations/botzone/` 的无贡适配误用为完整 Botzone 比赛制支持。

详细规则与测试边界见 `docs/`；变更前请先阅读 `AGENTS.md`。
