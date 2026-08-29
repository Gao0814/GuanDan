# 下一步提示词

执行 **Step L5-A4h8b：使用已安装的 Edge 浏览器扩展控制，自动完成全新 `43001/43002` 配对容量批次**。

项目所有者使用 Microsoft Edge，并负责在任务开始前完成登录、关闭旧桌和打开 Botzone 首页。必须使用当前已安装的 `chrome:control-chrome` 浏览器控制组件，并按其 Edge 专用选择器 `agent.browsers.get("edge")` 绑定 Microsoft Edge；该组件名称虽然包含 Chrome，但官方技能契约明确同时支持 Edge。不得改用通用 Windows `computer-use`、内置 Browser、Chrome family 或其他浏览器。

首次绑定 Edge 时完整阅读该浏览器组件的技能说明，初始化其浏览器运行时，精确调用 `agent.browsers.get("edge")`，随后完整读取 `edge.documentation()`。如果 Edge family 不可用，应报告浏览器扩展未连接并暂停，提示项目所有者检查 **Settings → Computer use** 与 Edge 中的 ChatGPT 浏览器扩展；不得回退到 `computer-use`、截图坐标、OCR 或另一浏览器。绑定成功后使用 Edge tab 的 URL、DOM、可见状态和 Playwright locator 做每一步 readback。

普通页面按钮点击、表单填写、connector、DeepSeek 调用和仓库外 evidence 写入均已默认授权，不要逐次询问。验证码、登录失效、遮挡或 Edge 未停在预期页面时，暂停并用一句话请项目所有者处理；等待不构成批次失败。

## 1. 项目所有者前置准备

开始自动执行前，仅确认以下人工准备已经完成：

- Edge 已登录 Botzone，并停在可见首页；
- 所有历史/额外本地 AI 测试桌已结束；
- 本地 AI 配置已提交，当前连接 URL/密钥有效；
- Edge 保持前台且窗口不最小化；
- 页面没有验证码、弹窗或其他遮挡。

首页资格必须同时满足：Edge tab 的 Botzone origin 合法、页面已登录、可见左上角 `Botzone 2026` 品牌和“创建游戏桌”入口。不得读取 Cookie、local storage、密码或连接密钥，不切换到其他浏览器。

若前置页面尚未准备好，只回复：

```text
请将 Edge 切到已登录的 Botzone 首页并保持前台，准备好后回复“已准备”。
```

不得因此创建 root、启动 connector 或判批次 invalid。

## 2. 封存旧批次

旧 root `D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002` 永久只读。旧判定保持：

```text
botzone_verified_ui_paired_policy_capacity_invalid
```

旧批次 completed=0，failure game 1 / `ui_readback`；不得清理、改写、重试或复用 `42001/42002`。

## 3. 创建全新正式批次

新 seeds/root：

```text
43001
43002
D:\VsCodeProject\BotzoneVerifiedUiCapacity-43001-43002
```

确认新 root 不存在。使用现有 `build_paired_schedule((43001, 43002), ...)` 生成固定 8 对/16 局：

| Game | Seed | Seat | Agent |
|---:|---:|---:|---|
| 1 | 43001 | 0 | rule |
| 2 | 43001 | 0 | deepseek |
| 3 | 43001 | 1 | deepseek |
| 4 | 43001 | 1 | rule |
| 5 | 43001 | 2 | rule |
| 6 | 43001 | 2 | deepseek |
| 7 | 43001 | 3 | deepseek |
| 8 | 43001 | 3 | rule |
| 9 | 43002 | 0 | deepseek |
| 10 | 43002 | 0 | rule |
| 11 | 43002 | 1 | rule |
| 12 | 43002 | 1 | deepseek |
| 13 | 43002 | 2 | deepseek |
| 14 | 43002 | 2 | rule |
| 15 | 43002 | 3 | rule |
| 16 | 43002 | 3 | deepseek |

每局生成唯一 32 位小写 hex token，以及独立 state/audit 路径。profile 固定为：需要进贡=否、级牌 2、载入上次配置中的同一三个 Bot 和同一上轮名次配置。budget 固定为 poll timeout 120、max cycles 100、max wall 3600、finished target 1、DeepSeek timeout 60/retries 0。

完整 payload 在内存校验 8 对/16 局、AB/BA 4/4、rule/deepseek 8/8、seat、路径和 token 唯一后才创建 root。manifest 使用 `O_EXCL temp → write → flush → fsync → close → replace → readback` 原子落盘。

创建 16 个空 state/audit 目录，并使用已验证 helper：

```text
C:\Users\86166\AppData\Local\Temp\botzone_progress_helper.py
```

原子创建 initial ready progress。helper 必须保持 9156 bytes / `de67b2d0e78aab328c6ca862981f6a8fa28a986d5e63ca7128669f681c492cbe`，不得修改或重跑 qualification。

## 4. 双模式零网络 preflight

在网页操作前分别执行一次 rule/deepseek `--preflight-only`。使用项目 `.venv`，进程启动前设置 `PYTHON_DOTENV_DISABLED=1`；每次要求 30 秒内 exit 0、唯一 `preflight_ready`、stderr 空、state 不变、无残留进程，全部 DNS/HTTP/Botzone/DeepSeek/connector/Agent/model 计数为 0。

两项通过后原子写低敏 `preflight-summary.json`。失败则用 helper 标记 `offline_preflight` invalid 并停止。

## 5. Edge 扩展自动循环

按 game 1→16 串行执行。每局固定使用以下循环；URL/DOM readback 仅用于证明仍在正确 Botzone 页面与确认表单值，不读取 Cookie、local storage、密码、连接 URL 或密钥。

### Edge 浏览器扩展初始化与恢复

首次控制 Edge 前按浏览器技能契约完成：

1. 初始化浏览器运行时并创建持久绑定 `edge = await agent.browsers.get("edge")`；禁止调用 `getDefault()`、`getForUrl()`、`get("chrome")` 或通用 extension fallback。
2. 立即完整读取 `edge.documentation()`，之后按该文档获取或绑定当前 Botzone tab。
3. 只在已绑定的 Edge tab 上执行 DOM/Playwright readback、点击和输入；每次页面转换后重新读取当前状态，不复用失效 locator。
4. 每个破坏性页面动作前确认 tab origin、当前页面阶段和唯一目标控件；普通建桌点击已默认授权。
5. Edge 扩展暂时断开时按浏览器技能的连接恢复流程处理；若仍不可用，暂停请项目所有者检查扩展，不创建 root、不启动 connector、不消耗 seed、不写 invalid progress。

不得通过 Windows Terminal、PowerShell、地址栏脚本、截图坐标、OCR 或 Edge 开发者工具做 UI 自动化；终端 connector 继续使用普通执行工具，与 Edge 浏览器绑定分离。

### A. 从首页创建 GuanDan 桌

1. 通过已绑定 Edge tab 的 URL、DOM 和可见状态确认处于 Botzone 首页，并确认可见 `Botzone 2026` 和“创建游戏桌”。
2. 点击“创建游戏桌”。
3. 在游戏选择界面选择 `GuanDan`，点击唯一“创建”。
4. 如出现验证码，暂停请项目所有者完成；完成后继续当前页面。
5. 看到“载入上次配置”和“开始游戏！”即判定到达 GuanDan 表单。

任何控件暂时未出现时先等待页面加载并刷新 tab 状态，不盲点、不切换浏览器。只有用户明确关闭桌或页面出现固定错误提示才按失败处理。

### B. 填写当前局配置

1. 点击一次“载入上次配置”。
2. 设置当前 game 的随机种子和本家 seat。
3. 确认“需要进贡=否”、级牌 2；三个 Bot 槽和上轮配置保持载入值，不复制或输出 Bot ID。
4. 通过当前 Edge tab 的 DOM 与可见表单值逐项确认配置正确。

配置控件无法唯一定位或 readback 不一致时暂停并保留当前页面；不要盲点，也不要因此判 invalid。

### C. 启动 connector 后开始游戏

配置确认后，使用 manifest 当前 game 的 agent/state/audit/token 启动唯一前台 PTY connector：

```text
python -m integrations.botzone
--agent <agent_mode>
--state-dir <state_dir>
--run-token <run_token>
--timeout-seconds 120
--max-cycles 100
--max-wall-seconds 3600
--stop-after-finished 1
--audit-file <audit_path>
```

必须取得持续 session ID；connector 不能立即退出。启动后等待页面显示本地 AI 已连接；随后再次用最新屏幕确认 seed/seat/no-tribute/level 未改变，再点击一次“开始游戏！”。

点击后不要再操作桌内按钮。保持 Edge 前台，等待 connector 自行完成。

### D. 对局结束并回首页

connector exit 0 / `finished_target` 且 evidence 验收通过后，读取最新 Edge tab 状态。对局结果页面出现后，只点击页面左上角品牌文字：

```text
Botzone 2026
```

等待回到显示“创建游戏桌”的首页，再开始下一局。不要点击桌内“继续”“退出”“关闭”或其他结果按钮。

## 6. 单局 evidence 与 progress

每局要求：

- connector exit 0 / `finished_target`；
- request=response=Header>0；qualified normal finished=1；
- 非 timeout transport failure=0，只允许守恒的 idle timeout diagnostic；其他 detail/profile 为空；
- v8 audit 与 v4 minimal tombstone 的 token/mode/path 匹配，无 active state；
- rule 局全部 `rule_primary`，model/fallback=0；
- deepseek 局至少 1 次 model success，全部 model result 为 success，fallback=0。

通过后用 helper `atomic_progress_write()` 将 completed 精确 +1；game 1..15 为 running，game 16 为 completed。不得手写 progress或跳号。

任一真实 connector/protocol/evidence 失败立即停止，不重试、不启动下一局，并用固定 stage 标记 invalid。Edge 扩展暂时断开、验证码、登录失效或页面控件暂不可读时只暂停请求项目所有者处理，不属于失败。

唯一失败判定：

```text
botzone_edge_ui_paired_policy_capacity_invalid
```

## 7. 最终聚合

16 局通过后，使用完整 schedule 调用 `aggregate_policy_audits()`：requested/valid=`8/8`，invalid/incomplete/duplicate=`0/0/0`，diagnostics 为空，每 seat=`2/2`，AB/BA=`4/4`。

原子写不含 seed/token/path/Bot/match/player/逐局内容的 `paired-report.json` 并做 canonical 回读与敏感扫描。

唯一成功判定：

```text
botzone_edge_ui_paired_policy_capacity_verified
```

最终只报告低敏逐局 evidence hash、聚合整数/Fraction、策略结果与模型 exposure/success/fallback。该 8 对结果仅为描述统计，不构成显著性、因果、动作质量或胜率提升结论。
