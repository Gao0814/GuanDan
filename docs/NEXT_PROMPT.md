# 下一步实施提示词

## Step L5-A4d2a：容量 manifest 恢复授权

L5-A4d1 未达到 ready，判定：

```text
botzone_paired_policy_capacity_recovery_preflight_invalid
```

### 已完成且可保留的前置

- 新容量根目录 `D:\VsCodeProject\BotzonePairedCapacity-25001-25002` 的仓库外、存在、为空和原子文件探针已通过；探针后恢复为空。
- L5-A4a/L5-A4b 检查点祖先关系和 L5-A4b 两文件提交范围通过。
- L5-A4b 定向 8 项、全量 612 项和 `git diff --check` 通过。
- 无 connector 残留；既有 `README.md` 改动未触碰。
- 旧容量目录未读取、未修改。

### 停止原因

调用现有 `build_paired_schedule((25001, 25002), conditions)` 的本地封装命令发生执行错误，且错误发生在任何文件写入前。按 L5-A4d1 的“不重试”规则，实施任务没有修正命令后重跑。

停止后确认：

- 新根目录文件数为 0；
- `capacity-manifest.json` 不存在；
- 16 个 state 子目录和 audit 目录均未创建；
- rule/deepseek preflight 均未启动；
- Botzone、DeepSeek、DNS/socket/HTTP、connector 和 Agent 调用均为 0；
- live 授权未请求、未消耗。

该结果是一次本地封装执行失败，不是 benchmark 测试失败，也不否定 seeds `25001/25002` 或新根目录。由于没有生成 artifact 或采集样本，可以在新的独立任务中保留相同 seed 和路径，但必须重新获得明确写入授权。

### 本步骤唯一动作

本步骤只向项目所有者请求 L5-A4d2b 授权，不执行工具、不运行测试、不写目录、不生成 manifest、不运行 preflight、不联网。

请项目所有者明确回复：

```text
我明确授权执行 L5-A4d2b：在仍为空的 D:\VsCodeProject\BotzonePairedCapacity-25001-25002 中，使用现有 build_paired_schedule((25001, 25002), conditions) 重新生成一次固定 capacity-manifest.json。允许先在内存中资格验证赛程，并通过单独的仓库外 Python 脚本执行一次原子 manifest 写入；不得运行 preflight、connector、Botzone 或 DeepSeek，也不得修改仓库文件或旧容量目录。
```

没有完整授权时保持：

```text
precondition_failed: capacity_manifest_recovery_authorization_missing
```

### L5-A4d2b 锁定边界

获得授权后的独立任务必须：

1. 只读复核新根目录仍存在且为空；非空时立即停止，不清理、不换路径。
2. 不重复 8/612 回归；只复核 HEAD、工作区和无 connector 残留。
3. 在仓库外创建一份短 Python runner，避免 PowerShell/`python -c` 多层转义；runner 不得包含 URL、key、Bot ID 或网络调用。
4. runner 先在内存中调用现有 `BenchmarkConditions` 与 `build_paired_schedule((25001, 25002), conditions)`，严格断言：8 对、16 局、四座位各 2 对、rule/deepseek 各 8、AB/BA 各 4。
5. 生成 canonical JSON，只保留 schema/version、固定 profile、seed、seat、策略顺序、game/pair 序号和预定相对 state/audit 名称；不得保存 Bot/match/player、URL/key、牌、history、action、prompt、RAG 或模型内容。
6. 通过同目录临时文件、flush/fsync 和 `os.replace()` 原子写入唯一 `capacity-manifest.json`；拒绝覆盖已有目标。
7. 写入后重新解析并验证完整结构，记录 bytes、SHA-256 和固定计数；不得输出 manifest 正文。
8. runner/manifest 失败即停止，不修正后重跑；只允许清理由本任务创建且名称固定的未完成临时文件，不得删除其他内容。

成功时唯一判定：

```text
botzone_paired_policy_capacity_manifest_recovery_verified
```

成功后 L5-A4d3 才创建 16 个隔离 state 子目录、audit 目录并执行 rule/deepseek 双模式零网络 preflight。L5-A4d2b 本身不得申请或执行 live。
