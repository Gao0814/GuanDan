# 下一任务提示词

## Step L5-A4f1：受权限监督的 direct connector 单局 pilot

本轮只执行一次全新的 Botzone 人工无贡 DeepSeek pilot，不修改仓库代码或测试，不复用任何历史 seed、state、audit、stream 或测试桌。

### 已锁定事实

- L5-A4e7 `27001`、L5-A4e8 `28001`、L5-A4e9 `29001` 均永久 invalid，不得重试或复用。
- Browser 扩展已经精确识别并绑定 `https://www.botzone.org.cn/` 的 Botzone 页面；不得退回依赖桌面截图猜测 URL。
- 统一执行工具已用完全离线的 20 秒 Python 进程验证可返回持续 session ID，并能在后续轮询中正常结束；执行工具并非天然不支持长进程。
- 当前进程中的 Botzone URL、DeepSeek key/base/model/timeout/retries 元数据均为 present 或匹配；不得输出其值、读取 `.env` 或记录敏感配置。
- `python-dotenv` 支持进程级 `PYTHON_DOTENV_DISABLED=1`；本次 connector 子进程必须显式设置该值。
- 使用合成 URL 和全新 D 盘仓库外目录的 `--preflight-only --agent rule` 已在系统扩展权限下返回 `preflight_ready`，目录最终为空。当前最具体的执行边界是：state/audit 位于 Codex 默认可写根之外，因此真正的 connector 进程本身也必须以系统扩展权限启动；不能只在父步骤创建目录后再用默认权限运行 connector。
- 这只是当前证据支持的主要边界，不把它表述为已经证明的唯一历史根因。
- 项目内计划操作已获项目所有者常驻默认授权；不要再次询问项目授权。系统权限确认和浏览器最终提交确认仍按平台安全要求执行，并明确说明不是项目授权。

### 固定参数

- seed：`30001`
- seat：`0`
- agent：`deepseek`
- run token：`9f866470c8d87008091fdbe5caf0eeb5`
- 新根目录：`D:\VsCodeProject\BotzoneEscalatedPilot-30001`
- state：根目录下全新空 `state`
- audit：根目录下不存在的 `audit\completion.json`
- Botzone：当前 `BOTZONE_LOCAL_AI_URL`
- DeepSeek：当前已核验 endpoint/model；timeout `60` 秒，retries `0`
- local-AI GET 上限：`100`
- connector wall 上限：`3600` 秒
- 完成 `1` 局即停
- 只允许一个 connector、一个人工网页测试桌；不调用 runmatch，不重试

### 执行顺序

1. 只读确认 HEAD 包含 `2209bb71e35c4142c28bf1218fb316f8cf67da2d`，工作区除项目所有者既有改动外没有新的代码/测试改动；确认无残留 connector。不得因无关 README/docs 改动清理或还原用户内容。
2. 使用系统扩展文件权限创建唯一新根目录及空 `state`；确认 completion audit 不存在。若根目录已存在、state 非空或 audit 已存在，直接 `precondition_failed`，不得清理后继续。
3. 不再创建新的 launcher、probe、driver 或诊断载体。若需要验证 state 边界，只允许使用现有 `python -m integrations.botzone --preflight-only`，并且该命令本身必须在与 live 相同的系统扩展权限下执行。不得联网探测或读取 `.env`。
4. 在唯一 PowerShell 子进程环境中设置 `PYTHON_DOTENV_DISABLED=1`、DeepSeek timeout `60`、retries `0`。不要输出 URL、key 或其他配置值。
5. 直接运行 `.venv\Scripts\python.exe -m integrations.botzone`，参数为 `--agent deepseek`、上述 state/token、poll timeout `120`、`--max-cycles 100`、`--max-wall-seconds 3600`、`--stop-after-finished 1` 与 completion audit。该命令必须：
   - 通过工具的 `require_escalated` 系统权限执行；
   - 使用 `tty=true`；
   - 初次 yield 后返回仍在运行的统一 session ID，且不得同时返回 exit code；
   - 不使用 `Start-Process`、detached 进程或 `live_launcher.py`；
   - 后续始终用同一个 session ID 轮询，不启动第二进程。
6. 如果 direct command 在取得 session ID 前退出，立即判 invalid。必须报告工具返回的真实 exit code 和固定 stdout/stderr 类别；不得只写“未取得 session ID”，不得重试。
7. 获得 session ID 后，使用 Browser 扩展打开已绑定的 Botzone 页面并监督“本地 AI 已连接”。在连接状态出现前不得创建桌。
8. 连接后填写一个全新 GuanDan 测试桌：需要进贡=`否`，本家座位=`0`，使用锁定 seed `30001`，其余参与 Bot 使用已核验的现有选择。只在最终“创建/提交”点击前请求一次浏览器动作确认；该确认是代表用户创建外部对局的即时确认，不是项目授权。
9. 提交后持续监督页面并轮询同一 connector session，直到进程自行结束或 3600 秒上限。不得因为聊天时序、state 首次出现或页面短暂刷新判失败；以进程、页面和最终 audit 为准。
10. 结束后只读验证 state/audit 聚合，不输出 URL、Header、match、token、手牌、prompt、模型响应或逐手内容。

### 验收

唯一通过判定：

```text
botzone_escalated_direct_connector_pilot_verified
```

必须同时满足：

- connector 自行 exit `0`，stop reason=`finished_target`；
- requests、responses、Headers 均为正且三者相等；
- `finished_qualified=1`，正常四人结果为 1；
- transport failures/timeouts 和全部协议 diagnostics/detail/profile 均为 0；
- v8 audit、v4 finished tombstone 与 manifest-less 固定 run token 一致；
- `agent_mode=deepseek`，决策来源/模型尝试/结果/fallback 守恒；
- 至少一次模型 `success` 进入最终合法响应；
- 无残留 connector；
- 未调用 runmatch，未创建第二桌。

任一条件失败时唯一判定：

```text
botzone_escalated_direct_connector_pilot_invalid
```

失败后不得重试、补采、复用 seed `30001` 或该根目录。若在建桌前失败，保留真实进程 exit/stdout/stderr 类别和空/非空 state/audit 事实；不要再增加诊断载体。

### 边界

- 本步不修改仓库文件，不运行完整回归，不形成 paired benchmark。
- 不读取或输出 `.env`、URL、API key、Header、Cookie、match ID、手牌、prompt、RAG 原文、模型响应或 run token。
- 该 pilot 即使通过，也只证明“受权限监督的 direct connector 能完成一局且模型动作被观测”；不证明 DeepSeek 优于 RuleBased、因果收益或胜率提升。
