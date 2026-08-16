# 下一步实施提示词

## Step L5-A4c1：容量试验人工前置恢复

L5-A4c 首次准入已停止，判定：

```text
precondition_failed
```

已确认：

- HEAD 包含 L5-A4a 检查点 `31e2fa5a474a377baa3fb80a4a427766623b96c7`；
- HEAD 包含 L5-A4b 检查点 `e1b4e14f2806b962c16a08434f8fef589bf9630b`；
- L5-A4b 提交范围精确为 benchmark 模块与对应测试；
- 无残留 connector；
- 项目所有者既有 `README.md` 改动未触碰。

本次停止发生在回归、容量清单、目录写入和 preflight 之前，因此不消耗任何网络或容量试验预算，也不否定 L5-A4a/L5-A4b。

### 当前只需要项目所有者提供两项输入

1. 明确确认：所有历史 Botzone 本地 AI 测试桌均已结束或关闭，当前没有活动测试桌。
2. 提供一个已存在、为空、仓库外的容量试验根目录绝对路径。

目录要求：

- 必须位于 `D:\VsCodeProject\GuanDan` 仓库之外；
- 必须是绝对路径；
- 必须已经由项目所有者创建；
- 当前必须为空；
- 不得复用历史 state、audit 或失败实验目录；
- 后续允许在其下创建 16 个隔离 state 子目录、preflight 子目录、audit 子目录和一份非敏感操作清单；
- 目录内不得预先放入 URL、密钥、`.env`、Bot ID、历史 audit 或其他对局数据。

如果需要在 PowerShell 中人工创建，可使用项目所有者自行选择的仓库外路径：

```powershell
$capacityRoot = "<仓库外绝对路径>"
New-Item -ItemType Directory -Path $capacityRoot | Out-Null
```

若目录已存在，必须人工确认它为空；不要使用递归删除命令清空已有目录。应改用另一个全新目录。

### 回复格式

项目所有者应直接回复：

```text
所有历史本地 AI 测试桌已全部结束：是
容量试验根目录：<已存在、为空、仓库外的绝对路径>
```

路径不是连接凭据，但不得把其内容或文件列表复制到仓库文档。

### 本步骤禁止事项

在两项输入均收到前：

- 不运行 8/612 回归；
- 不读取真实配置或 `.env`；
- 不创建、修改或扫描容量目录；
- 不生成赛程清单；
- 不运行 rule/deepseek preflight；
- 不启动 connector、创建测试桌或发送任何网络请求；
- 不申请 live 授权。

### 收到输入后的下一动作

两项输入齐全后，进入 L5-A4c2，并恢复原 L5-A4c 的顺序：

1. 只验证目录绝对、仓库外、存在、为空和可执行原子写探针；探针后仍为空。
2. 复跑 L5-A4b 定向 8 项、全量 612 项和 `git diff --check`。
3. 使用现有 `build_paired_schedule((24001, 24002), conditions)` 生成仓库外 canonical 操作清单并记录 bytes/SHA-256。
4. 分别执行一次 rule/deepseek 零网络 preflight。
5. 全部门槛通过后，仅提出覆盖 8 对/16 局的新批量 live 授权问题，不在同一步联网。

两项输入齐全前唯一结果保持：

```text
precondition_failed: paired_capacity_manual_inputs_missing
```
