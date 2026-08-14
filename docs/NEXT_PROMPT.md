# 下一步实施提示词

## Step L5-A2b11：长轮询 timeout 与 finished provenance 加固

上一轮唯一 live 判定永久记录为：

```text
botzone_deepseek_runmatch_no_tribute_smoke_invalid
```

runmatch 创建成功，direct-stage connector 完成 `requests/responses/headers=1/1/1`，协议 detail/profile 均为空；但唯一进程最终 exit 4 / `failure_limit`，cycles/successful=`8/2`，transport failures=6，finished raw/qualified=`1/0`。state 只剩最小 finished tombstone，无残留进程，且未重试。

该结果证明 direct-stage 解析与 Header 回传已进入真实平台闭环，但不证明 play 已确认、DeepSeek 已参与或对局完成。现有实现把 `TransportError` 全部折叠为 `transport_failure`，同时只记录 raw/qualified finished，无法安全区分长轮询空闲 timeout 和真正网络故障，也无法解释 raw finished 未 qualified 的类别。

官方本地 AI 说明明确指出 GET 可能持续等待到新 request 或 timeout，样例也把超时作为可继续轮询的情况。下一步直接修正运行时契约，不再增加仓库外诊断载体。

### 允许修改

- `integrations/botzone/http_transport.py`
- `integrations/botzone/connector.py`
- `integrations/botzone/runner.py`
- 与上述契约直接相关的 `tests/test_botzone_*.py`

禁止修改 protocol、poll、session、adapter、engine、agents、DeepSeek prompt/client、RAG、CLI、runtime config、上传 Bot、真实配置和 docs。不得联网、读取 `.env`、运行 preflight 或创建对局。

### Transport 契约

1. 公开固定 transport category allowlist；不得输出 URL、异常正文、状态正文、Header 或底层 exception chain。
2. `URLError.reason` 若为 `socket.timeout` / `TimeoutError`，必须规范化为 `timeout`；其他 URL/network 错误保持固定非敏感类别。
3. connector 只对精确 `TransportError` 读取 allowlist category；未知异常保持 `transport_failure` + 固定 `unclassified`，不得泄露类型或文本。
4. 长轮询 `timeout` 作为独立 `transport_timeout` / idle 计数：
   - 不增加 `transport_failures`；
   - 不增加 consecutive failure；
   - 不触发 `failure_limit`；
   - 仍受 `max_cycles` 与 `max_wall_seconds` 限制；
   - 不伪装为收到成功 poll payload。
5. 非 timeout 类别继续累计 `transport_failure`、固定 category、退避和 failure limit；成功 poll 必须重置 consecutive failure。
6. v4 既有 `diagnostics` 语义保持兼容；audit 可升版并新增 `transport_timeouts` 与固定 `transport_failure_categories`，不得删除或重命名既有字段。

### Finished provenance 契约

1. 不放宽现有 qualified 条件：仍必须是四人 finished、同 connector 实例、该 match 已有成功 ack 的 play Header、cleanup 成功且未重复计数。
2. 对 raw finished 增加互斥聚合：
   - aborted；
   - non-four-player；
   - four-player-unqualified；
   - qualified。
3. 分类总和必须等于 `finished_seen`；不得持久化 match ID、座位、分数或任何逐局内容。
4. raw finished 或 tombstone 不能单独触发成功；runner 仍只以 qualified finished 达成 `finished_target`。

### 必须覆盖的测试

- `socket.timeout`、直接 `TimeoutError`、`URLError(timeout)` 均归类 idle timeout。
- DNS/network、TLS、HTTP、redirect、invalid/oversized response 与未知 opener 错误仍是固定 failure category。
- 连续 timeout 不触发 failure limit，只由 wall/cycle limit 停止；timeout 后真实 failure 与成功 poll 的计数/重置正确。
- pending Header 遇 timeout 会恢复为 pending，后续成功 poll 只发送/ack 一次，不重复 Agent 或 effect。
- aborted、非四人、四人但无 ack play、四人且 ack play 四类 finished 互斥守恒。
- audit schema/JSON/不可变聚合、旧字段兼容和敏感词扫描。
- direct-stage、envelope、runner、finished provenance 与 DeepSeek runtime 相关回归保持通过。

### 验证与交付

运行新增定向测试、相关 Botzone 回归、全量测试及：

```text
git diff --check
```

通过后建立独立实现检查点，只提交允许的 integration/test 文件。唯一成功判定：

```text
botzone_long_poll_transport_contract_verified
```

本步骤不运行真实 preflight、connector、runmatch 或 DeepSeek，不请求 live 授权。完成后下一步才做一次零网络准入并重新请求单次 live 授权。
