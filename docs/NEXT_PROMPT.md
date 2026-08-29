# 下一步提示词

执行 **Step L5-A4h6b：修复 root 外 progress helper 的资格覆盖，并完成 rule/deepseek 双模式零网络 preflight**。

这是供新对话直接执行的完整交接。不要重新规划、不要再拆出诊断任务，也不要重复询问项目级授权。项目所有者已默认授权仓库外 qualification/scratch 文件、测试和零网络 preflight；系统权限弹窗仍按平台机制处理。本步骤不得启动 live connector、操作 Botzone 网页或发出任何网络请求。

## 1. 固定位置与只读基线

仓库：

```text
D:\VsCodeProject\GuanDan
```

正式批次 root：

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002
```

正式 artifact 基线：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `capacity-manifest.json` | 4661 | `5989a6dc07441c94b02725a31b29706d9708311ce7eee597e82b96b47921b4ff` |
| `progress.json` | 277 | `0517765bcdd4241c01eaca29bbb9d29e900a0890649ea3c45e5e251cc59745e2` |

`progress.json` 当前必须为：schema `botzone_verified_ui_capacity_progress`、version 1、status `ready`、total 16、completed 0、next 1、failed/failure 为 null，且 `manifest_sha256` 与上表 manifest hash 一致。

正式 root 当前必须满足：

- `games/game-01-*` 至 `game-16-*` 共 16 个预注册 game 目录；
- 16 个 `state/` 均为空；
- 16 个 `audit/` 均为空，completion audit 数为 0；
- 没有 `preflight-summary.json`、临时文件或未知 artifact。

正式 manifest 已是不可重写边界。不得修改、重建、格式化、迁移或补写 manifest，不得更换 seed `42001/42002`、game 顺序、mode、token 或路径。

## 2. 现有 helper 的精确交接

现有唯一 helper：

```text
C:\Users\86166\AppData\Local\Temp\botzone_progress_helper.py
```

当前基线：2280 bytes，SHA-256：

```text
9c5f207c7256aefff103e11147e353358b0f539e17e15d39bfef54a4650ad898
```

其固定 failure-stage allowlist 精确为：

```text
offline_preflight
lobby_gate
ui_readback
connector_start
table_submit
connector_run
evidence_validation
progress_write
final_aggregate
```

已确认的缺口：当前 `qualification()` 只执行 initial + 16 次完成转换，报告 `legal_transitions=17` 和 `failure_stages=9`；它没有实际执行 9×16 个 invalid 转换，也没有执行 malformed/终态/原子失败拒绝用例。因此上一步判定：

```text
precondition_failed: continuation_helper_qualification_failed
```

该失败没有接触正式 root，不使正式批次失效。

## 3. 本任务允许的修复

只允许原地修改上述 helper，并在同一临时目录新增一个明确命名的 qualification driver：

```text
C:\Users\86166\AppData\Local\Temp\botzone_progress_qualification.py
```

不得创建第二个 progress helper，不得把 helper/driver 写入仓库或正式 root。helper 可以增加严格校验、原子失败清理和 qualification-only 注入点，但运行时写 progress 的公开行为必须保持：精确九字段、固定 9-stage allowlist、canonical JSON、同目录 `O_EXCL` 临时文件、flush/fsync/replace/readback。

允许在 qualification 阶段反复修正 helper/driver，直到资格矩阵完整通过；这些修正发生在正式 root 外，不视为正式批次重试。不得因为 driver 的解析、导入、断言或覆盖缺口再次停止并另开诊断任务。只有确认 helper 本身无法满足锁定契约时才停止。

修改前后均记录 helper bytes/SHA-256；不得在 helper/driver 中写入正式 seed、token、URL、key 或正式路径。

## 4. 必须实现的资格矩阵

driver 必须由表驱动 registry 生成 expected case IDs，并在结束时断言 expected IDs 与 executed IDs 精确相等。case ID 只使用低敏类别和序号，不包含 stage 文本、路径、hash、seed 或 token。

### 合法路径

1. initial ready 校验 1 项。
2. game 1..16 连续完成 16 项；每次只能 completed+1，next 同步前移，第 16 项进入 completed。
3. 对 9 个锁定 failure stage × next game 1..16 执行 144 个 ready/running → invalid 转换；failed index 必须等于转换前 next，completed 保持当前前缀。
4. 每个合法写入均验证 canonical bytes、目标 readback、临时文件消失和九字段守恒。

### 拒绝路径

至少覆盖并逐项证明原目标 bytes/SHA-256 不变：

- top-level 非 object；九字段逐个缺失；未知字段；
- schema/version/status 类型错误与未知值；
- bool、字符串、float、负数、越界数冒充整数；
- manifest hash 非字符串、非 64 位小写 hex 或与绑定 hash 不同；
- total 不为 16；completed/next/failed/failure 的 null 与数值组合矛盾；
- 完成跳号、回退、重复、越过 16；completed/invalid 终态再次转换；
- unknown/non-string failure stage；failed index 不等于当前 next；
- 临时文件预先存在；write、flush、fsync、close、replace、readback 任一步骤注入失败。

所有原子失败路径都必须清理本次临时文件，不得覆盖既有合法目标，不得遗留半写文件。

## 5. 双次 qualification 的执行门槛

1. 对 helper 和 driver 运行 `py_compile`。
2. 使用两个全新、正式 root 外的 scratch 目录分别运行一次完整 qualification。
3. 两次必须 exit 0，expected/executed case count、分类计数、coverage bitmap/hash、最终结构 hash逐字段一致。
4. 必须明确报告 9 个 stage、16 个 game index、144 个合法 invalid 转换全部执行；所有拒绝 case 全部通过。
5. 两个 scratch 清空并删除；helper/driver 保留供后续正式 progress 更新。
6. qualification 前后重新核对正式 manifest/progress bytes/SHA-256、16 个空 state 和 0 个 completion audit，必须与第 1 节完全一致。
7. network、DNS、socket、HTTP、Botzone GET、DeepSeek request、transport、connector、Agent、model 调用均为 0。

如果修复后的 helper 行为仍无法通过完整矩阵，输出 `precondition_failed: continuation_helper_qualification_recovery_failed` 并停止；不得运行 preflight或写正式 progress。

## 6. 双模式零网络 preflight

qualification 通过后，按顺序各执行恰好一次：

1. `rule --preflight-only`
2. `deepseek --preflight-only`

要求：

- 使用项目 `.venv`；`PYTHON_DOTENV_DISABLED=1` 必须在进程启动前生效；不得读取 `.env`。
- 只检查 Botzone URL/DeepSeek key 为 present，endpoint/model/timeout=60/retries=0 匹配，不输出值。
- 使用 manifest 中各模式第一局对应的空 state 目录；不传 run token，不写 completion audit。
- 每次 30 秒内自行 exit 0，stdout 规范化为唯一 `preflight_ready`，stderr 空。
- preflight 前后 16 个 state 均为空、completion audit 仍为 0。
- DNS/socket/HTTP、Botzone GET、DeepSeek request、connector cycle、Agent action、`suggest_action_id()` 全为 0；无残留进程。

rule 失败时不执行 deepseek；任一模式失败不得重试或 live。使用已通过资格的 helper 将正式 progress 原子更新为 invalid：completed 0、next 1、failed 1、failure `offline_preflight`，输出：

```text
botzone_verified_ui_paired_capacity_preflight_invalid
```

## 7. 成功落盘与判定

双 preflight 通过后，在正式 root 原子创建唯一 `preflight-summary.json`。只保留固定 schema/version、manifest/helper/driver/coverage hash、qualification 原始计数、双 preflight 固定布尔值、inventory 守恒和零网络计数。不得包含 stage 名列表、seed、token、绝对路径、URL、key、环境值、命令行或异常正文。

成功时正式 progress 保持 initial ready，不启动 connector、网页桌或第 1 局。唯一判定：

```text
botzone_verified_ui_paired_capacity_preflight_ready
```

最终报告必须给出：helper/driver 与 summary 的 bytes/SHA-256、资格矩阵实际计数、双 preflight 结果、正式 artifact 前后 hash 不变，以及所有网络/connector/Agent/model 计数为 0。不要请求新的项目授权；下一任务才按 manifest 串行执行 16 局 live。
