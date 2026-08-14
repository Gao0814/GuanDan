# 下一步实施提示词

## Step L5-A2b7：runmatch 单局 DeepSeek live smoke

当前状态为 `botzone_deepseek_connector_local_preflight_ready`。本步骤等待项目所有者一次性提供 runmatch 输入并明确授权；在完整信息到齐前不得联网。

### 已通过门槛

- 使用项目 `.venv\Scripts\python.exe`。
- `PYTHON_DOTENV_DISABLED=1` 在文件解析前生效，未读取仓库 `.env`。
- preflight exit 0，stdout 单行 `preflight_ready`，stderr 空，用时 206 ms。
- 临时 state 前后为空并删除，无残留 connector。
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action、`suggest_action_id()` 均为 0。
- 工作区干净。
- 该结果只证明本地组合可构造，不证明外部服务可达。

### 项目所有者需一次性回复

```text
Bot ID 1：<可参与 GuanDan 的现有 Bot ID>
Bot ID 2：<可参与 GuanDan 的现有 Bot ID>
Bot ID 3：<可参与 GuanDan 的现有 Bot ID>
me 座位：<0|1|2|3>
旧本地 AI 测试桌已全部关闭：是
接受省略 X-Initdata，并在非零 tribute 或贡还阶段立即停止且不重试：是
```

三个 Bot ID 和 `me` 必须组成四个不同座位；runmatch Header 中必须恰好一个 `me`。Bot ID 只用于本次请求，不写入仓库、docs 或普通日志。

### 必须同时给出的明确授权

项目所有者的同一回复还必须包含：

```text
我明确授权执行 L5-A2b7：向由当前 BOTZONE_LOCAL_AI_URL 在内存中派生的 runmatch endpoint 发送一次 GET，并向当前 local-AI endpoint 最多发送 100 次 GET；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；只启动一个 connector，只创建一个 runmatch 对局，最长 3600 秒，完成一局即停。若首个请求显示非零 tribute，或出现 tribute/return，立即停止且不重试。
```

### 授权后的固定执行顺序

1. 复核工作区干净、配置元数据匹配、无残留 connector；不再重复完整回归。
2. 创建全新仓库外 state/audit；只记录聚合计数和固定诊断。
3. 使用项目 `.venv`、`PYTHON_DOTENV_DISABLED=1`、DeepSeek 60/0 启动唯一 connector。
4. 确认 local-AI poll 已连接后，派生 runmatch URL，仅发送一次：

```text
X-Game: GuanDan
X-Player-0..3: 三个 Bot ID 与恰好一个 me
```

不发送 `X-Initdata`。
5. 创建成功后不记录返回 match ID；等待 connector 处理该局。
6. 首个内层请求必须满足无贡 profile；否则 fail-closed。
7. DeepSeek 任意异常、超时或非法 action ID 走现有 RuleBased fallback；所有 response 仍必须来自 engine 原始合法 action ID/provenance。
8. 完成一个 qualified match、达到预算或出现固定失败后停止；不启动第二进程、不创建第二局、不补采。

### 验收边界

成功至少要求：runmatch 创建成功、非零 request/response/Header、qualified finished=1、transport failure=0、协议 diagnostics 为空、Botzone 无非法动作/决策超时、state 清理完成且无残留进程。

成功只能判定：

```text
botzone_deepseek_runmatch_no_tribute_smoke_verified
```

该结论只证明一次 Botzone/DeepSeek/RuleBased fallback 闭环可运行，不证明 DeepSeek 一定参与每手、动作质量或胜率提升。
