# 下一步实施提示词

## Step L4-A2c5b2a：独占创建目录范围矩阵独立恢复

请在 GuanDan 项目中执行 Step L4-A2c5b2a。本轮使用全新仓库外脚本、证据目录和目标目录，独立恢复三目录矩阵。L4-A2c5b2 永久保持 invalid，不补齐第三项、不复用部分结果形成结论。

本轮不修改仓库，不运行任何 preflight，不启动 launcher/connector，不永久修改环境变量，不联网，也不请求 live 授权。

### 已封板事实

- L4-A2c5a 检查点：`8ceb038d3dc6d6a4cfae3525b2bc92b2cc6da78c`，范围精确为三个文件；
- L4-A2c5b：`botzone_instrumented_live_preflight_invalid`；
- L4-A2c5b1：`botzone_state_tempfile_operation_boundary_verified`；
- L4-A2c5b2 执行时 HEAD：`8a535724bebc880cd54309c06bb663ba09f59d13`；
- L4-A2c5b2 唯一判定：`botzone_exclusive_open_scope_diagnosis_invalid`；
- L4-A2c5b2 qualification 成功；
- `configured_state` 与 `same_volume_fresh` 均得到 `PermissionError`、`errno=13`、`winerror=null`，候选不存在且目录最终为空；
- `local_appdata_fresh` 未执行，因为父载体错误地让第三目标目录与证据子目录同名；
- `summary.json`、`manifest.json` 未生成；因此前两项仅为不完整的部分证据，不能形成范围结论或系统根因结论；
- 全程 request/GET/network/connector/live-launcher 均为 0。

L4-A2c5b2 已产生证据必须只读保留：

- `exclusive_probe.py`：5,908 bytes，SHA-256 `469a2f9d9cc9f13f43e14cb289e57111e63edd2d43464bf0c71af2a9f7bf235b`；
- `driver.py`：5,341 bytes，SHA-256 `56773435ce97496b8485bc628cf047dc8dff683cf16bfd5b90e065d0859b4be3`；
- qualification audit：325 bytes，SHA-256 `1f61f6d523794aed15d8b518e403f884fff692c7ff83dc6fc7db0d88f78f3aba`；
- configured audit：434 bytes，SHA-256 `04f6d2e9aacf768539aaa6dd5b7e6d6ac1d79971885102f0b878c42e96305de4`；
- same-volume audit：435 bytes，SHA-256 `985384cfc729dab45a8f6e2df62a3f1e86446c6cc99ed3eccbaa5fa9065064ee`；
- 所有已产生 stdout/stderr：0 bytes，SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

### A. 前置门槛

1. 工作区干净，L4-A2c5a 检查点存在且范围不变；
2. 只读复核 L4-A2c5b、b1、b2 的既有证据，不修改、移动、补写、删除或放入新汇总；
3. 只确认 `BOTZONE_STATE_DIR` 为 present，不读取 `.env`；
4. configured state 存在且为空，只报告 `exists/empty`；
5. 没有残留 Botzone、preflight、launcher 或诊断进程；
6. 为本轮生成全新 run ID，并新建独立的仓库外 evidence root；
7. 本轮不得使用 L4-A2c5b2 的任何候选名、目录名或输出文件。

任一门槛失败即 `precondition_failed`。

### B. 路径拓扑资格验证

在执行任何 `os.open` 前，父载体必须先构造并验证以下路径角色：

- `evidence_root`
- `qualification_target`
- `configured_state`
- `same_volume_target`
- `local_appdata_target`
- 四个独立 evidence 子目录：qualification/configured/same-volume/local-appdata

硬门槛：

1. evidence 路径统一使用 `evidence-*` 前缀，目标路径统一使用 `target-*` 前缀；
2. 所有 resolve 后路径两两不相等；
3. 任一 evidence 路径都不得等于、包含或被任一 target 路径包含；
4. `same_volume_target` 与 configured state 同卷，但位于仓库外的全新独立目录；
5. `local_appdata_target` 位于本地应用数据区域，是全新独立目录；
6. qualification、same-volume、local-appdata 三个新目标在验证时必须尚不存在；
7. configured state 必须已存在且为空；
8. audit 只记录上述八项的 bool 结果和固定角色标签，不保存绝对路径、basename、环境值或哈希。

任何一项失败，判定 `botzone_exclusive_open_scope_recovery_precondition_failed`，不得创建目标目录或运行探针。

### C. 载体与异常脱敏

只在新 evidence root 创建标准库 runner/driver。不得导入 `integrations.botzone`。

每个目标只执行一个：

```text
os.open(candidate, O_CREAT | O_EXCL | O_RDWR, 0o600)
```

每个目标使用独立随机候选名且恰好执行一次。阶段固定为：

- `exclusive_open_started`
- `exclusive_open_completed` 或 `exclusive_open_failed`
- `close_completed`
- `cleanup_completed`

异常只持久化白名单类型、严格整数或 null 的 errno/winerror、filename presence bool 和 candidate existence bool。禁止保存异常文本、args、strerror、filename 值、环境值或路径。

每个子进程 15 秒硬上限；不重试。只清理本任务精确登记的候选和新目标目录，不使用通配符，不扫描或删除未知文件。

### D. 资格验证和独立矩阵

1. 先在 `qualification_target` 执行一次；必须 exit 0、完成 open/close/cleanup、目录清空且审计合法。
2. qualification 失败则判定 `botzone_exclusive_open_scope_recovery_harness_invalid`，不得运行矩阵。
3. qualification 通过后，按固定顺序各执行一次：
   - `configured_state`
   - `same_volume_fresh`
   - `local_appdata_fresh`
4. 每一项结束后必须确认子进程退出、精确清理完成，才能进入下一项。
5. 不得根据前一结果改变顺序、flags、超时、目录或采样次数。
6. 三项全部结束且清理完成后，必须先原子写 `summary.json`，再写 `manifest.json`；缺任一文件即 invalid。

旧 L4-A2c5b2 的 configured/same-volume 结果不得与本轮矩阵合并、平均或用来填补缺项。

### E. 判定

完整矩阵形成直接、可审计的失败范围：

```text
botzone_exclusive_open_scope_recovery_verified
```

三项均成功、未复现：

```text
botzone_exclusive_open_scope_recovery_not_reproduced
```

路径拓扑、qualification、三目标、summary/manifest、清理、进程、脱敏或计数任一不完整：

```text
botzone_exclusive_open_scope_recovery_invalid
```

`recovery_verified` 只允许按矩阵陈述：

- configured state 特异；
- configured 与同卷目标共同受影响、local-appdata 不受影响；
- 三目标均受影响；
- 或其他由完整三项直接支持的范围。

不得将范围升级为权限设置、杀毒软件、磁盘、Python、Windows 或安全策略根因。`PermissionError/errno=13` 只是异常分类，不是根因说明。

### 禁止事项

- 不运行 preflight；
- 不修改或永久设置 `BOTZONE_STATE_DIR`；
- 不修改仓库代码、测试或文档；
- 不启动 launcher、connector、transport 或 opener；
- 不联网；
- 不读取或显示 URL、密钥、真实目录路径；
- 不追认 L4-A2c5b2；
- 不因 local-appdata 成功而在本任务中迁移配置或恢复 live。

### 最终报告

报告必须包含：

- 执行 HEAD、工作区、L4-A2c5a 检查点范围；
- 旧 b/b1/b2 证据只读复核；
- 路径拓扑八项 bool 门槛；
- qualification 与三个固定标签的完整矩阵；
- 每项 exit、耗时、阶段、异常类型、errno/winerror、candidate existence、清理结果；
- runner、driver、各 audit/stream、summary、manifest 的 bytes/SHA-256；
- 所有新目标和 configured state 的最终 empty 状态；
- request/GET/network/connector/live-launcher count=0；
- 唯一判定和不归因声明。

后续是否迁移 state 目录或修改 preflight，必须依据本次完整恢复矩阵另开任务。
