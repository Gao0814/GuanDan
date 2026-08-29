# 下一步提示词

执行 **Step L5-A4h8：恢复可验证的 Chrome UI 控制通道，并在同一任务创建和执行全新 `43001/43002` 配对容量批次**。

不要重新解释历史失败，也不要拆成新的诊断/授权任务。项目所有者默认授权项目测试、仓库外 artifact、Botzone 页面必要点击、connector、DeepSeek 调用和本批次对局；不要重复询问项目级授权。验证码、登录失效或当前账号旧桌仍需要用户实际处理，但等待处理不构成失败。

## 1. 永久封存旧批次

旧 root：

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002
```

旧批次唯一判定永久保持：

```text
botzone_verified_ui_paired_policy_capacity_invalid
```

固定旧证据：

- manifest：4661 bytes / `5989a6dc07441c94b02725a31b29706d9708311ce7eee597e82b96b47921b4ff`
- preflight summary：2273 bytes / `32a9cf1adfdc881037aea6adb8f594a51876a958df88fc0a4432ddf55370cad9`
- progress invalid：285 bytes / `d6396eb7f644c29045f1a3f4ff7ee6544e3a2cd2938a673e755bc75ee6d5eb68`
- game 1 audit：695 bytes / `2bccc78a92ea7bf361c68b8860f51ff213e0d8220ce776a9ca0eb31b77a01d76`
- completed prefix 0/16；failure game 1 / `ui_readback`；game 1 state 空，其余 15 局未触碰。

旧 root 全程只读：不得删除、清理、重试、补采、改写 progress 或复用 `42001/42002`、token、路径和 audit。

## 2. 根因边界与浏览器控制策略

旧失败不是 connector/协议/DeepSeek 失败：页面未提交，connector 为 0/0/0、exit 130。失败来自语义浏览器控制失去响应，随后错误切换到无法可靠确认 URL 的 Windows 视觉控制。

本任务只允许使用能直接返回真实 tab URL 和 DOM/可访问性状态的浏览器控制通道：优先 `chrome:control-chrome`。开始前读取该 skill 的 `SKILL.md` 并按其契约操作。

- 禁止使用 OCR/截图文字猜测 URL。
- 禁止在同一表单流程中切换到 Windows 视觉控制继续点击。
- 若 Chrome 中没有已登录 Botzone 页面，只要求用户在 Chrome 打开并登录 `https://www.botzone.org.cn/game/GuanDan`，随后恢复同一任务；不要判 invalid。
- 浏览器插件暂时失联时，可在没有正式 root、没有 connector、没有桌提交的资格阶段重连并重新执行 UI 资格；这不消耗 seed。
- 所有普通页面按钮点击已默认授权，不再逐次询问；只有验证码由用户完成。

## 3. 正式 root 创建前的 Chrome UI 资格

此阶段不得创建新 root、manifest、progress、state/audit，不启动 connector，也不发送 DeepSeek 请求。

1. 用 Chrome controller 枚举当前 tab，选择 URL origin 精确为 `https://www.botzone.org.cn` 的已登录页面，并记录不含 query/账号信息的页面类型。
2. 连续三次读取同一 tab 的真实 URL 与关键 DOM，每次间隔至少 2 秒；tab ID、origin 和登录状态必须稳定。
3. 从主页进入“创建游戏桌”→唯一 GuanDan 选择→唯一“创建”；如出现验证码，暂停等待用户完成，然后继续同一 tab。
4. 到达 GuanDan 表单后点击一次“载入上次配置”，只读确认：需要进贡=否、级牌 2、上轮名次 profile 和三个非本家 Bot 槽已填充。
5. 将未提交表单临时设置为 seed 43001、local seat 0；连续三次通过真实 DOM readback 精确确认 seed/seat/no-tribute/level/profile/Bot 槽。
6. 不点击“开始游戏！”，不启动 connector；再次读取真实 URL，确认仍为同一建桌表单。

资格期允许修正 locator、等待页面加载、重新连接 Chrome controller 或让用户完成验证码，直到上述门槛明确通过；不得因工具瞬时失败消耗正式 batch。无法获得可验证 URL/DOM 时输出 `precondition_failed: chrome_ui_control_unavailable`，且新 root 必须仍不存在。

资格成功中间判定：

```text
botzone_chrome_ui_control_ready
```

通过后保留当前已准备的 game 1 表单，并在同一任务继续下一节。

## 4. 创建全新正式批次

新 seeds/root：

```text
43001
43002
D:\VsCodeProject\BotzoneVerifiedUiCapacity-43001-43002
```

开始前要求新 root 不存在。只有第 3 节 UI 资格通过后才生成完整 manifest payload；payload 在内存全部验证后才创建 root。

### 固定 schedule

使用现有 `build_paired_schedule((43001, 43002), ...)` 生成 8 对/16 局，agent 顺序必须为：

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

为每局生成唯一 32 位小写 hex run token 和独立 `state/`、`audit/completion.json` 路径。profile/budget 锁定为无贡、级牌 2、同一上轮名次/对手 profile、poll timeout 120、max cycles 100、max wall 3600、finished target 1、DeepSeek 60/0。

manifest schema 以旧 manifest 只读作为形状参考，但内容必须由新 schedule/token/path 重新生成；不得复制旧 token。验证 pair/game index、seed×seat、AB/BA 4/4、rule/deepseek 8/8、路径唯一、token 唯一和 canonical bytes/hash后，按 `O_EXCL temp → write → flush → fsync → close → replace → readback` 原子创建 manifest。

创建 16 个 game/state/audit 目录并验证为空。通过已验证 helper：

```text
C:\Users\86166\AppData\Local\Temp\botzone_progress_helper.py
```

原子创建 initial ready progress。helper 当前锁定为 9156 bytes / `de67b2d0e78aab328c6ca862981f6a8fa28a986d5e63ca7128669f681c492cbe`；不得重跑 qualification或修改 helper。

## 5. 新批次双 preflight

分别执行恰好一次 rule/deepseek `--preflight-only`，使用新批次对应空 state，项目 `.venv`，并确保 `PYTHON_DOTENV_DISABLED=1` 在启动前生效。每次要求 30 秒内 exit 0、唯一 `preflight_ready`、stderr 空、state 仍空、无残留进程，DNS/socket/HTTP/Botzone/DeepSeek/connector/Agent/model 全为 0。

两项通过后原子写低敏 `preflight-summary.json`。任一失败则用 helper 原子标记 progress invalid / `offline_preflight`，停止且不 live。

## 6. 每局 Chrome + connector 固定流程

严格 game 1→16 串行，前局 evidence 和 progress 通过后才开始下一局。

1. 使用同一 Chrome controller 和真实 URL/DOM。game 1 复用第 3 节表单；后续每局重新进入 GuanDan 建桌表单并载入上次配置。
2. 设置当前 seed/seat/no-tribute/level/profile；第一次 DOM readback全部匹配。
3. 在 connector 启动前再次进行三次稳定 URL/DOM readback。资格不稳定时只重连浏览器，不启动 connector、不判 batch invalid。
4. 启动当前 game 唯一前台 PTY connector，必须取得持续 session ID；参数从 manifest 读取：agent、state-dir、run-token、audit-file，timeout 120、cycles 100、wall 3600、finished 1。
5. 轮询同一 connector；页面明确显示已连接后执行第二次完整 DOM readback。
6. 只点击一次“开始游戏！”，随后 Browser 只读，不点击结束/返回/继续/关闭/桌内按钮。
7. 等待同一 connector 自行退出并验收 evidence。

connector 启动后语义控制若失联，禁止切换 Windows 视觉控制继续点击。若尚未提交桌，先尝试重连同一 Chrome tab；connector 仍运行且 URL/DOM 恢复后可继续。connector 已退出、tab 无法唯一归属或页面状态无法证明时整批停止，不启动第二 connector。

## 7. 单局 evidence 与 progress

每局必须满足：exit 0 / `finished_target`；request=response=Header>0；qualified normal finished=1；非 timeout transport failure=0；仅允许守恒的 idle timeout diagnostic；其余 detail/profile 为空；v8 audit 与 v4 minimal tombstone 的 token/mode/路径匹配且无 active state。

- rule：全部 `rule_primary`，model/fallback=0。
- deepseek：至少 1 次 model success，全部 model result 为 success，fallback=0。

通过后用 helper `atomic_progress_write()` 将 completed 精确 +1；game 1..15 为 running，game 16 为 completed。不得手写 progress、跳号或重复推进。

任一真实失败立即停止，不重试该局、不启动下一局；保留 evidence，并以固定 stage 原子标记 invalid。唯一失败判定：

```text
botzone_verified_ui_paired_policy_capacity_recovery_invalid
```

## 8. 最终聚合

16 局通过后使用完整正式 schedule 调用 `aggregate_policy_audits()`：requested/valid=`8/8`，invalid/incomplete/duplicate=`0/0/0`，diagnostics 为空，每 seat=`2/2`，AB/BA=`4/4`。

原子写不含 seed/token/path/Bot/match/player/逐局内容的 `paired-report.json`，回读 canonical JSON并做敏感扫描。

唯一成功判定：

```text
botzone_verified_ui_paired_policy_capacity_recovery_verified
```

最终只报告低敏逐局门槛、evidence bytes/SHA-256、聚合整数/Fraction、策略结果和模型 exposure/success/fallback。该 8 对结果仅为描述统计，不构成显著性、因果效果、动作质量或胜率提升结论。
