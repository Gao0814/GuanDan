# 下一步实施提示词

## Step L5-A2b16：网页人工无贡桌单次 live 授权

L5-A2b15 已完成：

```text
botzone_finished_tombstone_cleanup_verified
```

固定 state 现为空；L5-A2b14 的脱敏聚合 audit 保持 996 bytes、SHA-256 `fca58e8210aa3dcd11941500bfd7954c2327a111d8b59cd786d85b5b60c5e03f`。本路线永久停止使用 `runmatch`，改为 connector 已连接后由项目所有者在 Botzone 网页人工创建一个无贡测试桌。

### 项目所有者需一次性确认

```text
所有历史 Botzone 本地 AI 测试桌均已关闭：是
本次只创建一个新的 GuanDan 测试桌：是
我会在 connector 显示已连接后再建桌：是
建桌时选择“需要进贡=否”并选择“用本地 AI 替代我”：是
若网页建桌失败、出现非零 tribute 或 tribute/return，将立即停止且不重试：是
```

### 必须同时给出的明确授权

```text
我明确授权执行 L5-A2b16：不调用 runmatch endpoint；使用当前 BOTZONE_LOCAL_AI_URL 启动唯一一个 deepseek 模式 connector，向 local-AI endpoint 最多发送 100 次 GET，单次 Botzone GET timeout 为 120 秒；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；最长运行 3600 秒，qualified finished=1 即停。connector 显示已连接后，我会在网页手动创建且只创建一个“需要进贡=否”的 GuanDan 测试桌，并明确确认页面已进入对局。若建桌失败、出现非零 tribute、tribute/return、固定协议错误或非 timeout transport failure 达到现有上限，立即停止且不重试。v5 audit 只保存聚合计数和固定分类，不保存 URL、密钥、match、手牌、history、prompt、response 或模型正文。
```

旧授权均已消耗，不能替代以上确认和授权。Botzone URL、DeepSeek key 与其他敏感值只从当前进程环境读取，不写入 docs、audit 或普通日志。

### 授权后的固定执行顺序

1. 快速确认工作区干净、无 `integrations.botzone` 残留进程、固定 state 为空、既有 L5-A2b14 audit 未改变；不重复项目测试或 preflight。
2. 只核对 Botzone URL/key 为 present，DeepSeek endpoint/model/timeout/retries 与授权匹配；不得输出值或读取 `.env`。
3. 在独立 audit 目录创建一个全新且不存在的 v5 audit 文件名；不得覆盖 L5-A2b14 audit。
4. 使用项目 `.venv`、`PYTHON_DOTENV_DISABLED=1`、`--agent deepseek` 启动唯一 connector；不得构造或请求 runmatch URL。
5. connector 启动后先通知项目所有者等待页面状态。只有项目所有者回复“已连接”后，才允许其人工创建新桌。
6. 项目所有者在网页设置 GuanDan、“需要进贡=否”、“用本地 AI 替代我”，其余席位选择测试 Bot；只创建一个桌，并回复“人工新桌已创建并进入对局”。
7. connector 自动处理该桌请求。任何 `tribute` / `return`、非零 tribute、协议诊断或非法动作均 fail-closed；DeepSeek 异常或非法 action ID 只允许既有 RuleBased fallback。
8. qualified finished=1、预算耗尽或固定失败时停止；不启动第二进程、不创建第二桌、不重试或补采。
9. 进程结束后验证 v5 audit、finished 分类守恒、state 只剩允许的最小 tombstone、无残留进程与敏感形态；不得在同一步清理 tombstone。

### 验收判定

只有同时满足以下条件，才能判定：

```text
botzone_manual_no_tribute_deepseek_mode_smoke_verified
```

- 项目所有者确认 connector 已连接，并确认网页人工新桌已创建且进入对局；
- runmatch request count 精确为 0；
- local-AI request、response、Header 均非零；
- qualified finished 精确为 1，其他 finished 分类与总数守恒；
- 协议 diagnostics/detail/profile 为空；
- 非 timeout transport failure 为 0；
- 无非法动作、Botzone 决策超时或残留进程；
- state/audit 符合既有安全边界。

任何门槛失败都只能判定对应 `invalid` / `precondition_failed`，且不得重试。由于 v5 audit 尚不记录模型成功调用次数，该结论只证明 deepseek 模式 connector 的人工桌协议闭环，不证明 DeepSeek 实际参与每手、动作质量或胜率提升。
