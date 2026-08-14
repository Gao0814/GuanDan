# 下一步实施提示词

## Step L5-A2b5a：required-fields profile 实现检查点封存

本任务只复核并提交工作区中已经完成的 L5-A2b5 七个源码/测试改动。不得修改这些文件内容，不得修改 docs，不得运行 preflight，不得读取真实配置，不得联网、启动 connector 或调用 DeepSeek。

### 当前状态

- 当前 HEAD：`43d4b6fd4dbb55556de8e68163d63fc791a0982e`。
- L5-A2b5 已判定 `botzone_required_fields_shape_profile_verified`。
- 已知工作区只应包含以下七个未提交文件：

```text
integrations/botzone/bot_io.py
integrations/botzone/poll.py
integrations/botzone/connector.py
integrations/botzone/runner.py
tests/test_botzone_request_diagnostics.py
tests/test_botzone_live_preflight.py
tests/test_botzone_finished_provenance.py
```

- 六种固定 profile 与 audit v4 契约已经过离线复核。
- 上一次 L5-A2b6 因检查点不存在而得到 `precondition_failed: required_fields_profile_checkpoint_missing`；未运行回归、preflight 或网络操作。

### 执行边界

1. 先检查 `git status --short`，文件集合必须与上述七项精确相同。
2. 检查完整 diff，确认没有未报告的行为、敏感数据、真实请求、URL、密钥、match、牌或日志内容。
3. 不得编辑、格式化或重写任何源码、测试或 docs。
4. 运行：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_finished_provenance -q
python -m unittest discover -q
git diff --check
```

5. 任一回归、补丁检查或提交范围检查失败时停止，不得提交，报告明确失败原因。
6. 全部通过后，只 stage 上述七个文件并创建单独提交；建议提交信息：

```text
Add safe Botzone required fields profiles
```

7. 提交后复核：

```text
git show --stat --oneline --summary HEAD
git status --short
```

提交范围必须精确为七个文件，工作区必须为空。

### 禁止事项

- 不修改或提交任何 `docs/` 文件；
- 不读取 `.env`、Botzone URL、DeepSeek key 或其他配置值；
- 不创建 state/audit 目录；
- 不运行 `--preflight-only`；
- 不发送 Botzone GET、DeepSeek 请求或任何网络探测；
- 不启动 connector，不创建或加入测试桌；
- 不请求 live 授权。

### 验收

通过时唯一判定：

```text
botzone_required_fields_profile_checkpoint_verified
```

完成报告必须包含：完整提交 hash、精确提交文件、定向/全量测试计数、`git diff --check`、提交后工作区状态和零网络声明。

本任务结束后停止。下一阶段才是 L5-A2b6 零网络 v4 preflight；不得在本任务中顺带执行。
