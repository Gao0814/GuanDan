# 下一步实施提示词

## Step L5-A4e1：失效容量批次 state 审计与清理

25001/25002 容量批次在第 1 局即停止，规范化判定：

```text
botzone_paired_policy_capacity_batch_invalid
```

### 固定事实

- 项目所有者已人工创建并进入第 1 桌，但当时唯一 Python connector 已不在运行。
- game 1 completion audit 不存在。
- game 1 state 目录已有 1 个活动文件，不能视为空白、完成或可重试对局。
- 第 1 局不满足 exit 0、`finished_target`、独立 v7 audit 的预注册门槛。
- 第 2–16 局均不得启动；第 1 局不得重启、补采或迁移计分。
- 项目所有者已确认网页第 1 桌关闭。
- 该失败归因边界是 connector 生命周期没有覆盖人工桌完整对局，不归责于人工建桌操作；当前证据不足以断言 connector 为何提前结束。

项目所有者的常驻默认授权继续有效。本步骤不得再次询问 state 审计或精确清理授权；只有操作系统权限审批可由平台提示。

### 本步骤范围

本步骤只做零网络、只读资格审计和在资格通过后的单文件精确清理。不得运行测试、preflight、connector、Botzone、DeepSeek，不得修改仓库、manifest、game audit 或其他 state 目录。

### 执行要求

1. 只读复核 HEAD、工作区和 manifest：3256 bytes，SHA-256 `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`。
2. 残留检查只枚举 `python.exe/pythonw.exe`，并要求独立参数 `-m integrations.botzone`；不得匹配 PowerShell/Codex/检查命令自身。发现 connector 时停止，不终止进程。
3. 严格复核容量布局：game 1 completion audit 不存在；game 1 state 精确只有 1 个普通文件；game 2–16 state 均为空；全部 16 个 game audit 目标均不存在。任何额外文件、目录或链接立即停止。
4. 只解析 game 1 的唯一 state 文件，不输出原文。必须验证当前 session schema/version、文件名与内部 session key 一致、路径属于预注册 game 1 state、finished 不存在，并记录固定低基数聚合：stage、delivery、pending response/effect、handler/cached response 的存在性。
5. 若 state malformed、已 finished、文件归属不一致、存在未知字段/对象、或无法证明它只属于已关闭的 game 1，则判 invalid 并原样保留，不尝试修复或删除。
6. 资格通过后，依据项目所有者“网页桌已关闭”和常驻授权，只对已登记的精确文件执行一次非递归删除；不得删除目录、manifest、其他 state 或任何 audit。
7. 删除后验证 game 1 state 文件数从 1 变为 0，16 个 state 目录均为空，manifest bytes/hash 不变，16 个 game audit 目标仍不存在。
8. 在容量根的 audit 父目录写入一个固定命名、与 16 个 game audit 目标不冲突的脱敏 cleanup audit。仅记录 schema/version、批次失效、game index、删除前后计数、固定状态分类、manifest hash、零网络计数和检查布尔值；不得记录 session/match/player、牌、history、response、digest、路径或异常正文。
9. 输出 cleanup audit 的 bytes/SHA-256，并复核无敏感字段。任何失败都不得重跑、扩大删除范围或继续新批次。

### 判定

全部通过时唯一判定：

```text
botzone_paired_policy_failed_game_state_cleanup_verified
```

否则唯一判定：

```text
botzone_paired_policy_failed_game_state_cleanup_invalid
```

成功后将 `25001/25002` 与当前容量根目录永久只读封存，不再作为容量样本。下一步 L5-A4e2 才离线设计 connector 存活握手和新的 seed/root；不得直接启动新批次。
