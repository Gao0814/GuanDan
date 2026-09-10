# 给 Coding Codex 的下一任务 Prompt

你负责执行一次独立、可恢复的固定 Botzone workspace 旧 evidence 清理。不要修改仓库文件，不要运行测试、preflight、connector、Botzone、Edge、网络、Agent或模型，不要创建Git commit。清理完成后停止，不要在同一任务中开始下一局live。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`。项目所有者已经在 `AGENTS.md` 中长期授权：规划Codex完成上一轮审计并写入文档后，可清理 `D:\VsCodeProject\BotzoneWorkspace` 内已核对的旧artifact，无需再次请求授权。

本任务只允许Windows回收站式可恢复操作；不得永久删除，不得清空回收站，不得使用递归删除、通配符或扩大到其他目录。全部检查和回收必须在同一个PowerShell控制面内完成，不跨shell拼接路径。

## 【当前项目状态】

decision trace实现已由规划Codex独立复核并提交为：

```text
045fb75 feat: record acknowledged Botzone decisions
```

独立验证为Botzone定向88项、主规则39项、全量707项通过。下一次live需要新的 `history.txt` 与 `decision-trace.json`，因此必须先单独回收seed `47002`的旧evidence。

规划Codex在2026-09-10只读复核的预期现场：

- `D:\VsCodeProject` 下唯一以 `Botzone` 开头的直属目录是普通非链接目录 `D:\VsCodeProject\BotzoneWorkspace`；
- workspace顶层精确包含普通非链接目录 `audit`、`state`、`streams`，以及文件 `history.txt`；
- 五个旧文件为：

| 相对路径 | bytes | SHA-256 |
| --- | ---: | --- |
| `audit\completion-audit.json` | 818 | `068ff687ce7d7a1d02114637ba0d4bbe1875493f35dd46799b8ad0bc5a27b708` |
| `history.txt` | 8146 | `7d786b1640bfa8d0d747a74fb01eafdee19ff6e0516ee60167757e00ea5b94d0` |
| `state\fa8dbb17486ade96de29840b182b3c8cc8abfb7020fbdb816ba0ccbcbf60cf26.json` | 115 | `5313a2007ae344139770c86ca978e4c9b6aabd27c2f3c8dea3b750ec3f5df309` |
| `streams\stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `streams\stdout.txt` | 58 | `e990db21b8510eb12cecb343c57155c4fa68cbb4ac07c42143ee226a5a2c96e6` |

这些文件已经完成结果与策略审计，可以回收。目录 `audit/`、`state/`、`streams/` 必须保留并最终为空。

## 【本次任务目标】

在全部只读门槛精确匹配后，把上述五个文件逐个移入Windows回收站，并验证workspace最终精确只剩三个空目录：

```text
D:\VsCodeProject\BotzoneWorkspace\audit
D:\VsCodeProject\BotzoneWorkspace\state
D:\VsCodeProject\BotzoneWorkspace\streams
```

## 【执行前门槛】

在任何回收动作前一次性验证：

1. 仓库 `git status --short` 为空，并记录当前HEAD；如果不为空，停止且不改任何文件。
2. `D:\VsCodeProject` 下以 `Botzone` 开头的直属目录集合精确为 `BotzoneWorkspace`。
3. workspace根及三个子目录都是普通目录、非符号链接/联接点/reparse point。
4. workspace递归inventory除三个目录和表中五个文件外没有其他项目。
5. 五个文件均为普通非链接文件，bytes与完整SHA-256逐项匹配。
6. 没有正在运行且可安全归属于本项目Botzone connector的进程；检查时不得输出命令行、URL、token或其他敏感参数。

任一门槛不匹配都必须停止，实际回收数为0；不要自行修复inventory、删除未知项或请求新的授权。

## 【回收方式与安全边界】

- 使用Windows回收站API，例如 `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile(..., SendToRecycleBin)` 的精确单文件调用。
- 对五个已验证绝对路径逐个处理；不得使用 `Remove-Item`、`rm`、`del`、递归参数、目录删除或通配符。
- 不得删除或移动workspace根及 `audit/`、`state/`、`streams/`。
- 如果某个文件回收失败，立即停止后续回收，报告已完成与未完成的精确低敏清单；不要重试其他删除机制。
- 不得清空回收站。

## 【完成后验证】

1. 五个旧文件原路径全部不存在。
2. workspace递归inventory精确为三个普通非链接空目录。
3. `D:\VsCodeProject` 下仍只有一个 `Botzone*`直属目录。
4. Git HEAD与完整 `git status --short` 前后一致且为空。
5. 没有启动connector、浏览器、网络、preflight、Agent/model或测试。

## 【完成标准】

- 五个精确旧文件均进入Windows回收站，未永久删除；
- 三个固定空目录保留；
- 没有inventory drift、仓库变化或其他运行副作用；
- 本任务在清理报告后结束，不分配seed、不启动下一局。

## 【执行后的报告要求】

最终报告必须包含：

1. 固定判定：成功时使用 `botzone_workspace_seed_47002_evidence_recycled`；
2. 六项执行前门槛是否全部通过；
3. 五个回收文件的相对路径、bytes和SHA-256；
4. 最终workspace精确inventory；
5. Git HEAD/status前后一致性；
6. 是否执行永久删除或清空回收站（预期均为否）；
7. connector、浏览器、网络、preflight、Agent/model和测试调用计数（预期均为0）；
8. 明确说明下一seed尚未分配，本任务未开始live。
