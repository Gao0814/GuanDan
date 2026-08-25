# 下一步实施提示词

## Step L5-A4e9：direct persistent connector 单局 pilot

L5-A4e8 已停止，唯一判定：

```text
botzone_persistent_session_launcher_pilot_invalid
```

### 已确认边界

- seed `28001` pilot 的 launcher 启动未返回可持续 session ID，随后退出；state/audit 为空、两个 stream 为 0 bytes，未进入页面连接或建桌。该 seed/root 永久只读。
- 现有证据仍不能确定 launcher 具体退出原因，不得继续修改 launcher 或建立新的启动诊断载体。
- 随后使用项目 `.venv` 完成一次完全离线的统一执行 session 资格：合成长进程在 10 秒 yield 后返回 session ID `45404`，跨工具调用继续运行，最终输出 completion 并 exit 0。该结果证明 Codex 当前执行工具支持持续前台会话。
- Edge Browser 扩展已成功识别并绑定标题 `Botzone`、URL `https://www.botzone.org.cn/` 的现有标签页。
- `integrations.botzone.__main__` 本身已经支持 `--agent`、`--state-dir`、`--run-token`、预算与 v8 audit；在持续执行 session 下不再需要 `live_launcher.py` 的 Windows stream 重定向层。

项目所有者常驻项目授权继续有效。最终点击浏览器“创建测试桌”前仍按浏览器安全规则做一次即时动作确认；不得再次询问 Botzone/DeepSeek 项目授权。

### 目标

使用全新 seed `29001`、seat `0`、`deepseek`，直接在 Codex 持续前台统一执行 session 中运行现有 connector 入口，完成恰好一局人工无贡 pilot。该步骤不修改代码、不使用 launcher、不计入 paired benchmark。

### 固定预算

- 新仓库外根目录：`D:\VsCodeProject\BotzoneDirectPilot-29001`，开始时必须不存在或为空。
- token 由 canonical `direct-pilot/29001/seat0/deepseek` 的 SHA-256 前 32 位派生，不输出。
- 一个 direct connector 进程、一个统一执行 session、一个网页桌、一个 state 和一个 v8 audit；不创建 launcher stream 文件。
- Botzone GET 最多 100 次；poll timeout 120 秒；wall 3600 秒；finished 1；不重试。
- DeepSeek 使用锁定 endpoint/model，timeout 60 秒、retries 0；禁止 runmatch、CLI 对局和 probe。
- 桌面固定：无贡、级牌 2、seed 29001、本家座位 0，其余 profile 与成功人工 smoke 一致。

### 执行

1. 核对 HEAD、工作区、无残留 connector、配置脱敏元数据和精确 Botzone Browser 标签页；不得读取 `.env`、URL、key、Cookie 或账号信息。
2. 原子创建全新空 state 与缺失 audit 目标；根目录有未知内容立即停止。
3. 使用统一执行工具直接前台运行：

   ```text
   .venv\Scripts\python.exe -m integrations.botzone
   ```

   并显式传入 `--agent deepseek`、state、run token、timeout/cycle/wall/finished 和 audit。必须启用持续会话能力并设置约 10 秒初始 yield；禁止 `live_launcher`、Start-Process、后台 job、`&`、分离子进程或未等待 promise。
4. 只有启动工具返回非空 session ID 且无 exit code 才可继续。若直接退出，完整保留该次工具返回的固定 exit code 与脱敏 output category，立即判 invalid；不得建桌或重启。
5. 用同一 session ID 做一次空轮询确认仍运行，再 claim Botzone 标签页。浏览器动作前后继续用同一 ID 检查存活。
6. 页面显示本地 AI“已连接”后，Codex 填写唯一 GuanDan 无贡桌、seed 29001、seat 0 与固定 profile。最终点击创建前做一次即时浏览器动作确认；确认后只点击一次。
7. 对局期间交替监控 Browser 与统一执行 session，直到 direct connector 自行退出；不得启动第二进程或创建第二桌。
8. 完成门槛：exit 0、`finished_target`、request=response=Header 且大于 0、qualified finished=1、零 transport failure/timeout、空 diagnostics/detail/profile、正常四人结果、agent mode deepseek、全部观测守恒。
9. v8 audit 与 v4 最小 tombstone 的 token 必须与派生 token 一致；state 仅留该 tombstone。统一执行输出只能含固定 connector 完成行，stderr 不得有异常。
10. DeepSeek outcome/fallback 守恒；允许 model exposure=0。仅输出脱敏聚合和 artifact bytes/SHA-256，不输出 token、URL、Header、ID、牌、动作、prompt 或模型内容。

### 判定

全部通过：

```text
botzone_direct_persistent_connector_pilot_verified
```

任一 session、Browser、动作确认、协议、transport、结果、v8/v4/token 或敏感边界失败：

```text
botzone_direct_persistent_connector_pilot_invalid
```

失败不得复用 `29001`。成功后先离线清理 tombstone，再以全新 seed/root 规划 paired capacity；pilot 不进入策略比较。
