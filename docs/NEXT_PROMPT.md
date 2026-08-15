# 下一步实施提示词

## Step L5-A2b21：简化人工网页无贡桌单次 live 授权

L5-A2b20 已完成：

```text
botzone_failed_manual_session_cleanup_verified
```

L5-A2b19 残留 session 经严格验证为 `play/inflight`，pending response/effect 与 handler/cached response 存在、finished 不存在；在项目所有者关闭网页桌并明确放弃恢复后，已精确删除。state 目录现为空。新脱敏 cleanup audit 为 564 bytes，SHA-256 `7abc9fdc7b8590b522295cc321d8c4317ce04bdab04e1fd7fa32f6207fbabf8e`，既有 audit 保持不变。

本次永久禁用 runmatch，也取消“聊天确认到达前 state 必须为空”的门槛。实施任务成功启动唯一 connector 后，只回复：

```text
connector_running_create_one_table_when_page_connected
```

项目所有者收到该消息后，在 Botzone 页面显示“已连接”时直接创建且只创建一个无贡 GuanDan 测试桌；state 变为非空是预期行为。进入对局后再回复：

```text
人工新桌已创建并进入对局
```

### 项目所有者需一次性确认

```text
所有历史 Botzone 本地 AI 测试桌均已结束或关闭：是
本次只创建一个新的 GuanDan 测试桌：是
我会等到实施任务回复 connector_running_create_one_table_when_page_connected，并在页面显示“已连接”后直接建桌：是
建桌时选择“需要进贡=否”并选择“用本地 AI 替代我”：是
进入对局后我会回复“人工新桌已创建并进入对局”：是
若页面未连接、建桌失败、出现非零 tribute 或 tribute/return，将立即说明且不创建第二桌：是
```

### 必须同时给出的明确授权

```text
我明确授权执行 L5-A2b21：不调用 runmatch endpoint；使用当前 BOTZONE_LOCAL_AI_URL 启动唯一一个 deepseek 模式 connector，向 local-AI endpoint 最多发送 100 次 GET，单次 Botzone GET timeout 为 120 秒；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；最长运行 3600 秒，qualified finished=1 即停。实施任务回复 connector_running_create_one_table_when_page_connected 后，我会在页面显示“已连接”时人工创建且只创建一个“需要进贡=否”的 GuanDan 测试桌，并在进入对局后回复“人工新桌已创建并进入对局”。state 在 connector 启动后变为非空属于预期，不再以聊天确认到达时间判失败。若页面未连接、建桌失败、出现非零 tribute、tribute/return、固定协议错误或非 timeout transport failure 达到现有上限，立即停止且不重试。v5 audit 只保存聚合计数和固定分类，不保存 URL、密钥、match、手牌、history、prompt、response 或模型正文。
```

旧授权均已消耗，不能替代本次授权。不得读取或输出 Botzone URL、DeepSeek key、Header、Cookie、match 或 `.env` 内容。

### 授权后的固定执行顺序

1. 确认 HEAD 包含 `5bb44fd4052e181d08455594ab0879c0ee305dfb` 和当前文档检查点，工作区干净，无 `integrations.botzone` 残留进程，固定 state 为空，三份既有脱敏 audit 不变；不重复测试或 preflight。
2. 只核对 Botzone URL/key 为 present，DeepSeek endpoint/model/timeout/retries 与授权匹配；使用项目 `.venv` 与 `PYTHON_DOTENV_DISABLED=1`，不得加载 `.env`。
3. 在独立 audit 目录选取一个全新且不存在的 v5 audit 文件；不得覆盖或修改旧 audit。
4. 使用既有已验证 launcher 启动唯一 `--agent deepseek` connector：100 cycles、Botzone timeout 120、wall 3600、stop-after-finished 1；禁止构造或请求 runmatch URL。
5. 只有 connector 进程成功存活后，回复 `connector_running_create_one_table_when_page_connected`。如果进程在该消息前退出，直接 invalid，不允许建桌。
6. 项目所有者看到 Botzone 页面“已连接”后直接创建唯一 GuanDan 桌，选择“需要进贡=否”和“用本地 AI 替代我”，进入对局后回复固定确认。无需在建桌前再次等待聊天许可；state 0→1 不构成失败。
7. connector 自动处理请求。任何 `tribute` / `return`、非零 tribute、协议诊断或非法动作均 fail-closed；DeepSeek 异常、timeout 或非法 action ID 只允许既有 RuleBased fallback。
8. 即使 connector 在项目所有者确认消息到达前退出，也不得仅凭消息时序判 invalid；应等待项目所有者说明是否已建桌，再结合 v5 audit 作唯一判定。不得重启进程。
9. qualified finished=1、预算耗尽或固定失败时停止；不启动第二进程、不创建第二桌、不重试或补采。
10. 结束后验证 v5 audit、finished 分类守恒、state 只剩允许的最小 tombstone、旧 audit 不变、无残留进程和敏感形态；不得在同一步清理新 tombstone。

### 验收判定

只有以下门槛全部满足，才能判定：

```text
botzone_manual_no_tribute_deepseek_mode_smoke_verified
```

- connector 启动前 state=0、旧桌全部关闭，runmatch request=0；
- 项目所有者确认只创建一个无贡桌，且页面已进入对局；
- 该桌 local-AI request、response、Header 均非零；
- qualified finished 精确为 1，其他 finished 分类与总数守恒；
- 协议 diagnostics/detail/profile 为空；
- 非 timeout transport failure 为 0；
- 无非法动作、Botzone 决策超时或残留进程；
- state/audit 符合既有安全边界。

任何门槛失败只能判定对应 `invalid` / `precondition_failed`，不得重试。现有 v5 audit 不记录模型成功调用次数，因此该结论只证明以 deepseek 模式运行的人工桌协议闭环，不证明 DeepSeek 实际参与每手、动作质量或胜率提升。
