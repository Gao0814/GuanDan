# 下一步实施提示词

## Step L5-A4d2c：容量 manifest runner 导入恢复授权

L5-A4d2b 未达到 verified，规范化判定：

```text
botzone_paired_policy_capacity_manifest_recovery_invalid
```

### 已确认事实

- 新容量根目录 `D:\VsCodeProject\BotzonePairedCapacity-25001-25002` 仍存在且为空，文件数为 0。
- `capacity-manifest.json` 及其临时文件均不存在。
- 未创建 16 个 state 子目录或 audit 子目录。
- 仓库外 runner 在导入项目 `evaluation` 模块时退出；失败发生在内存赛程生成和任何 manifest 写入之前。
- 未运行 rule/deepseek preflight、connector、Botzone、DeepSeek、DNS/socket/HTTP 或 Agent。
- 仓库未修改；既有 `README.md` 改动未触碰。

L5-A4d2b 不得重试或追认为通过。由于没有生成 artifact、写入状态或采集样本，seed `25001/25002` 和同一空容量根目录仍可用于新的独立恢复任务。

### 本步骤唯一动作

本步骤只请求一次新的 L5-A4d2d manifest 写入授权；不执行工具、不创建 runner、不写目录、不运行测试/preflight，也不联网。

请项目所有者明确回复：

```text
我明确授权执行 L5-A4d2d：在仍为空的 D:\VsCodeProject\BotzonePairedCapacity-25001-25002 中，使用全新的仓库外 Python runner，从已核验的仓库根 D:\VsCodeProject\GuanDan 显式设置仅本次子进程使用的项目模块导入路径，调用现有 build_paired_schedule((25001, 25002), conditions)，并原子生成一次 capacity-manifest.json。不得修改仓库或持久环境变量，不得安装包、复制项目源码、运行 preflight/connector、访问 Botzone/DeepSeek，也不得读取或修改旧容量目录。
```

没有完整授权时保持：

```text
precondition_failed: capacity_manifest_import_recovery_authorization_missing
```

### L5-A4d2d 锁定边界

获得授权后的独立任务必须：

1. 只读确认 HEAD、工作区、无 connector 残留，以及新容量根目录仍存在且完全为空；失败即停止，不清理、不换路径。
2. 不重复 8/612 回归；L5-A4d1 已完成的测试证据继续有效。
3. 在系统临时目录创建全新仓库外 runner 和独立资格目录；不得把 runner 或资格 artifact 写入容量根目录。
4. runner 启动时只对该子进程把已核验仓库根加入模块搜索路径；不得修改用户/系统 `PYTHONPATH`、`.pth`、虚拟环境、源码或 Git 工作区。
5. 在写入容量根目录前先完成导入资格：`evaluation.botzone_policy_benchmark` 的 module spec/origin 必须解析到已核验仓库根，且成功导入 `BenchmarkConditions` 与 `build_paired_schedule`。只记录布尔值和固定阶段，不记录完整路径或异常正文。
6. 资格通过后在内存中生成赛程，并严格断言 8 对、16 局、四座位各 2 对、rule/deepseek 各 8、AB/BA 各 4，seed 仅为 `25001/25002`。
7. 生成 canonical JSON，只保留 schema/version、固定 profile、seed、seat、策略顺序、game/pair 序号和预定相对 state/audit 名称；不得保存 URL/key、Bot/match/player、牌、history、action、prompt、RAG 或模型内容。
8. 通过同目录固定临时文件、flush/fsync 和 `os.replace()` 原子写入唯一 `capacity-manifest.json`；目标或临时文件已存在时拒绝覆盖。
9. 写入后重新解析并验证完整结构，记录 bytes、SHA-256 和固定聚合计数；不得输出 manifest 正文。
10. runner、导入资格、赛程断言或写入任一失败即停止且不得修正后重跑；只允许清理由本任务创建且已登记的临时 runner/资格文件，不得删除容量根目录中的未知内容。

成功时唯一判定：

```text
botzone_paired_policy_capacity_manifest_import_recovery_verified
```

成功后才进入 L5-A4d3：创建 16 个隔离 state 子目录和 audit 目录，并执行 rule/deepseek 双模式零网络 preflight。L5-A4d2d 本身不得申请或执行 live。
