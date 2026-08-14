# 下一步实施提示词

## Step L5-A2b6d：简化配置修复与 runmatch 实测准备

本任务停止新增诊断载体，直接使用现有安全错误分类修正本地配置，直到零网络 preflight 通过。只有真实 Botzone/DeepSeek 请求继续采用单次授权和固定预算；纯本地 preflight 允许在每次明确修正后重新运行。

### 已确认基线

- profile 检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- 安全诊断契约检查点：`3f2cadb7f242625ca0978c5b47a5bc6f5ed299e7`。
- 定向 26 项、全量 578 项和补丁检查已通过。
- L5-A2b6d 尚未执行；此前 L5-A2b6、L5-A2b6a/b 的 invalid 结果保留，但不再约束新的纯本地 preflight 必须“一次失败永久停止”。
- Botzone 官方与用户提供的文章均确认 `runmatch`：把本地 AI URL 最后一段 `localai` 改为 `runmatch`，发送 GET，并使用 `X-Game`、`X-Player-0..n` 和可选 `X-Initdata`；玩家中必须恰好一个 `me`。
- 参考：[Botzone 官方本地 AI](https://wiki.botzone.org.cn/index.php?title=%E6%9C%AC%E5%9C%B0AI)、[用户提供的快速创建对局文章](https://blog.csdn.net/sinat_37574187/article/details/145495160)。

### 第一阶段：直接修复本地配置

1. 不修改代码，不创建新的诊断脚本。
2. 必须使用项目虚拟环境解释器，不得使用 PATH 中不确定的系统 `python`：

```text
D:\VsCodeProject\GuanDan\.venv\Scripts\python.exe -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-state-dir>
```

3. 在同一个 `.venv` 解释器中只读确认 `dotenv.main.load_dotenv` 支持 `PYTHON_DOTENV_DISABLED`，且禁用判断发生在 `DotEnv` 创建和文件解析之前。不得读取 `.env`。
4. 子进程显式设置：

```text
PYTHON_DOTENV_DISABLED=1
DEEPSEEK_TIMEOUT=60
DEEPSEEK_MAX_RETRIES=0
```

项目 `.venv` 中的 `python-dotenv` 已确认会在读取文件前处理该开关并直接返回；`config.py` 无需自行识别它。不得读取仓库 `.env`，不得输出 URL、key 或路径值。
5. 根据固定输出直接处理：
   - `preflight_runtime_config_missing`：补齐当前进程缺失的 Botzone URL 或 DeepSeek 必需变量；
   - `preflight_runtime_config_url_invalid`：从 Botzone 本地 AI 配置页重新复制完整 HTTPS URL，仅写入进程环境；
   - timeout/response/failure/backoff invalid：恢复代码已锁定的正数参数，DeepSeek 保持 60/0；
   - state directory/operation invalid：换用全新系统临时目录；
   - `preflight_agent_composition_failed`：只检查显式 DeepSeek endpoint/model/key/60/0 与本地 RAG 文件可读性；
   - `preflight_configuration_error`：报告固定类别和本地阶段，不再搭建新载体。
6. 每次只修正当前固定类别对应的一项配置，然后可重新运行纯本地 preflight；本地运行不设“仅一次”限制。
7. 每轮必须保持 Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 和 `suggest_action_id()` 全部为 0。
8. 达到 exit 0、单行 `preflight_ready`、stderr 空、state 清理完成后停止本地调试。

本阶段通过判定：

```text
botzone_deepseek_connector_local_preflight_ready
```

### 第二阶段：runmatch 快速建桌准备

preflight 通过后，不立即联网。先向项目所有者收集并确认：

1. 三个可参与 GuanDan 的现有 Bot ID；
2. 本地 AI `me` 所在座位 `0..3`；
3. 所有旧本地 AI 测试桌已关闭；
4. 接受 `X-Initdata` 暂不发送：官方只说明它可选，尚未给出 GuanDan“需要进贡=否”的确定编码。

计划中的单次 runmatch 请求：

```text
GET <由当前 localai URL 在内存中替换末段得到的 runmatch URL>
X-Game: GuanDan
X-Player-0: me 或 Bot ID
X-Player-1: me 或 Bot ID
X-Player-2: me 或 Bot ID
X-Player-3: me 或 Bot ID
```

必须恰好一个 `me`。URL、Bot ID、返回 match ID 和响应正文不得写入仓库、docs 或普通日志。

由于未发送 `X-Initdata`，创建后的首个请求必须验证 `global.tribute == 0`。若收到 `tribute`、`return` 或非零 tribute，立即 fail-closed，结束该局，不以空响应、pass 或随意牌绕过。

### 第三阶段：新的 live 授权

在发起任何外部请求前，必须取得一次新的明确授权，覆盖：

- 向 Botzone 发送一次 `runmatch` GET 以及最多 100 次 local-AI GET；
- 向 `https://api.deepseek.com` 的 `deepseek-v4-flash` 发送本家未公开手牌、公开局面、合法候选、评估/记牌摘要、场景标签和 RAG 片段；
- DeepSeek timeout 60 秒、retries 0；
- 一个 connector、一个 runmatch 对局、最长 3600 秒、完成一局即停；
- 若对局不是无贡，立即停止且不重试。

未获得三个 Bot ID、座位、旧桌清理确认和完整授权前，不得联网。获得后应先启动 connector，确认 Botzone 显示已连接，再发送唯一 runmatch 请求。

本任务不新增诊断载体，不修改 runtime，也不预先宣称 DeepSeek 可达、动作质量或胜率提升。
