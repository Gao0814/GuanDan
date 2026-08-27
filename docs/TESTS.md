# GuanDan 测试与验收

## 2026-08-14 Botzone required-fields profile 回归

已执行：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_finished_provenance -q
Ran 36 tests - OK

python -m unittest discover -q
Ran 574 tests - OK

git diff --check
OK（仅 Git 的 LF/CRLF 提示）
```

静态边界扫描只命中普通列表的 `requests.append`，未发现新增网络客户端、`.env`/真实配置读取、Cookie、DeepSeek 调用、引擎私有状态或上传产物改动。

注意：用户报告的 30 项定向集合已通过；本次规划复核扩大到 36 项，额外覆盖 poll、connector、runner 与 finished provenance。七个实现/测试文件仍待实现任务独立提交。

后续 L5-A2b6 首次准入因检查点缺失在测试前停止，因此没有新增测试运行结果，也没有 preflight 或网络计数。下一步 L5-A2b5a 将在不修改文件的前提下重新执行同一 36/574 回归，成功后只提交七个实现/测试文件。

L5-A2b5a 复核已完成：定向 36 项、全量 574 项和 `git diff --check` 通过；七个文件已提交为 `8e8d639011bd095bcf0af74816609c63e8c6199f`，提交后工作区干净。该步骤未运行 preflight，网络与模型请求为 0。

L5-A2b6 再次复核同一 36/574 基线并通过。唯一零网络 preflight exit 2，stderr 为空，state 前后为空并删除，无残留进程；Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 和 `suggest_action_id()` 均为 0。该失败不是测试失败，而是本地 preflight 配置/组合阶段未通过。

L5-A2b6a 未重跑 preflight 或测试。唯一仓库外 process-only 诊断以 `runtime_config_invalid` 结束，审计仅含固定阶段 `runtime_config_load_started` 和零网络计数；未进入后续 state、AppConfig 或 Agent 阶段，且无残留 state 或子进程。

L5-A2b6b 同样未运行仓库测试或正式 preflight。合成载体资格返回 `diagnostic_harness_invalid`，真实配置子阶段未执行；stdout/stderr、state、残留进程和所有网络/模型计数均为空或 0。该结果属于诊断载体失败，不是 runtime-config 测试结论。

L5-A2b6c 定向 26 项、全量 578 项和 `git diff --check` 通过。测试锁定 runtime config 六类、state 两类、Agent composition、通用回退、成功 stdout、exit code 和非 preflight 兼容；全部使用合成配置，真实 preflight 与网络计数为 0。

流程调整后不再把零网络 preflight 的单次失败永久封存。每次本地运行仍必须保持全部网络/模型计数为 0，并仅根据固定 stdout 类别修正一个配置项。真实 runmatch/local-AI/DeepSeek 请求仍必须单独授权且不重试。

dotenv 禁用能力已通过项目 `.venv` 内安装源码只读复核：`load_dotenv()` 在任何 `DotEnv` 创建或文件解析前检查 `PYTHON_DOTENV_DISABLED` 并返回。系统 `python` 与 `.venv` 的 dotenv 版本不同，后续命令必须显式使用 `.venv\Scripts\python.exe`；该复核未读取 `.env` 或配置值，网络计数为 0。

最终受监督本地 preflight 使用项目 `.venv`：exit 0、stdout=`preflight_ready`、stderr 空、206 ms；临时 state 前后为空并删除，无残留进程，Botzone/DeepSeek/DNS/socket/HTTP/transport/connector/action/suggestion 计数均为 0。该结果不是 live 或外部可达性测试。

L5-A2b7 已收到完整输入与 live 授权，本轮文档更新未新增测试运行。实际 smoke 必须验证：runmatch 仅请求一次、恰好一个 `me`、重复 Bot 组合若被拒绝则不重试、首请求无贡、非零 request/response/Header、qualified finished=1、零 transport/protocol failure、state 清理和无残留进程；任何不满足项均不得判为 verified。

L5-A2b7 实际运行未达到上述门槛：runmatch 成功但 requests/responses/headers=`1/0/0`，画像为 direct inner-stage candidate，未进入 session/Agent/DeepSeek。L5-A2b8 的离线回归必须同时覆盖 envelope 与 direct-stage 两种 wire mode，尤其锁定 mode 绑定的 Header 编码、direct deal/play session 连续性、pending/ack/restart、冷启动 play 拒绝、unsupported stage 和 envelope 兼容；实现步骤不得联网。

L5-A2b8 已通过双模式定向 68 项、全量 583 项和 `git diff --check`，检查点为 `2cd208b9b8f7306decf3182318fb55278c09d641`。测试确认 direct deal/play 原始 response、envelope wrapper、malformed stage、冷启动 play、unsupported stage、注入、pending 重发/ack 和 provenance 边界。本实现阶段网络计数为 0；L5-A2b9 不重复全量测试，只执行一次零网络 preflight。

L5-A2b10 live 得到 requests/responses/headers=`1/1/1`、协议诊断为空，但 6 次未分类 transport failure 触发 failure limit，raw/qualified finished=`1/0`。L5-A2b11 离线测试必须锁定 timeout 不占 failure budget、其他 category 仍 fail-closed、pending Header 在 timeout 后只 ack 一次，以及四类 finished provenance 的互斥守恒；不得降低 qualified finished 条件或联网。

L5-A2b11 已通过定向相关 80 项、全量 587 项和 `git diff --check`，检查点为 `220c648a4629453621f534beaeb95e52d85656ce`。测试覆盖 timeout/URLError timeout、其他 transport category、failure budget/重置、pending Header、四类 finished provenance、v5 audit 兼容与敏感边界。实现阶段网络计数为 0；L5-A2b12 不重复测试，只运行一次零网络 preflight。

L5-A2b12 因系统临时 state 目录无法创建而在子进程启动前返回 `precondition_failed`；没有新增测试或网络活动。L5-A2b12a 仍不重复 80/587 测试，只在获批的仓库外临时目录运行原零网络 preflight，并验证 state 前后为空、固定 stdout、零网络计数和无残留进程。

L5-A2b12a 在受限写入下仍未创建 state 或启动 preflight，网络计数继续为 0。L5-A2b12b 不新增测试，由项目所有者在宿主机 PowerShell 运行一次现有 `--preflight-only`；验收仅看单行 `preflight_ready`、exit 0、state_empty=True、stderr 空，不接受 live 结果替代。

L5-A2b12b 在创建新仓库外资源前再次 `precondition_failed`，没有新增测试或网络活动。L5-A2b12c 使用只读确认存在且为空的既有 `D:\VsCodeProject\BotzoneState`，只运行一次零网络 preflight；不得创建 audit、删除目录或以 live 结果替代准入。

L5-A2b12c 因独立 audit 路径不可用在首次 GET 前停止，网络计数为 0。L5-A2b12d 不运行仓库测试或项目代码，只由项目所有者在固定仓库外 audit 目录执行 `{}` 探针的创建、同目录重命名、删除，并验收目录最终为空。

L5-A2b12d 宿主机探针结果为 exists=True、empty=True、passed，未运行项目或网络。L5-A2b12e 不重复测试，只运行一次 `--preflight-only`，并要求固定 stdout、exit 0、state/audit 均为空、stderr 空和零网络行为。

L5-A2b12e 实际得到 `preflight_ready`、exit 0、state/audit 均为空，stderr 未显示；判定本地零网络准入通过。没有新增测试运行或网络计数。L5-A2b13 live 必须验收 v5 timeout/failure/finished 聚合、direct-stage response、qualified finished 和敏感边界，且需新授权。

L5-A2b13 未产生可用 v5 完成 audit：唯一 connector/runmatch 尝试后页面无对局，connector 被终止，state 非空且未读取/清理。该结果属于 live 验收失败，不是测试失败。L5-A2b14 不运行项目回归或网络，只验证只读 session 聚合、未知数据 fail-closed、敏感字段不落盘，以及 state 目录在审计前后的文件数、总字节数和目录摘要完全一致。

L5-A2b14 未运行项目测试、preflight 或网络。只读审计确认 completion audit 缺失，state 有 1 个合法 finished tombstone；所有 active-session 聚合为 0，前后目录摘要一致。聚合 audit 通过固定 schema/value allowlist 和敏感形态白名单扫描；该结果不替代 live 验收。L5-A2b15 不运行测试或网络，只复核同一 audit/tombstone 后做一次精确、非递归删除，并验收 state 为空、audit 不变。

L5-A2b15 未运行项目测试、preflight 或网络。删除前唯一文件严格为 finished tombstone，删除后 state 文件数为 0；L5-A2b14 audit 的 996 bytes 与 SHA-256 保持不变。L5-A2b16 不重复回归/preflight，live 验收新增 runmatch request=0、connector 已连接人工确认、网页新桌进入对局人工确认、无贡 stage、非零 request/response/Header、qualified finished=1 和 v5 安全边界。

L5-A2b16 live 在人工新桌确认前以 `history_alignment_failed` 停止：request/response/Header=`4/3/3`，finished=0，transport timeout/failure=0。L5-A2b17 离线测试必须新增完整四项零重叠窗口替换，同时保留重复、最长 overlap、短窗口零重叠拒绝、pending/ack、重启、adapter observation 与 envelope/direct 等价性；实现和测试不得读取残留 live state 或联网。

L5-A2b17 已通过定向 17 项、相关 65 项、全量 590 项和 `git diff --check`。测试确认完整四项无 overlap 全量追加、初期短 latest 到完整 incoming、短 incoming 拒绝、重复/最长 overlap、累计 history 超过四项、latest 上限四项及 envelope/direct 等价。实现检查点为 `5bb44fd4052e181d08455594ab0879c0ee305dfb`，未读取 live state 或联网。L5-A2b18 不运行测试，只做授权后的严格单文件 state 处置。

L5-A2b18 未运行测试、preflight 或网络。唯一旧 session 经当前 schema 验证为 `play/idle`、无 pending/effect/finished 后被单文件删除；state 目录为空，两份 audit 不变。L5-A2b19 不重复 590 项回归/preflight，新增验收门槛为握手前 state=0、runmatch=0、人工已连接/建桌双确认、无贡 stage、非零 request/response/Header、qualified finished=1、零协议诊断与零非 timeout transport failure。

L5-A2b19 因 state 在聊天确认到达前变为 1 而按门槛停止；该现象发生在用户已操作网页、但确认消息尚未送达的窗口，故属于握手验收失败，不是代码测试结论。L5-A2b20 不运行测试或网络，只对唯一残留 session 做严格 schema/key/path 验证、脱敏聚合审计和授权后的单文件删除；后续 live 不再把确认消息前 state=1 作为失败条件。

L5-A2b20 未运行测试、preflight 或网络。唯一 `play/inflight` session 在用户关闭桌面并放弃 pending response 后，经 schema/key/path 与敏感边界验证精确删除；state 文件数 1→0，新 cleanup audit 为 564 bytes、SHA-256 `7abc9fdc7b8590b522295cc321d8c4317ce04bdab04e1fd7fa32f6207fbabf8e`。L5-A2b21 不重复回归/preflight，验收以启动前 state=0、用户单桌承诺、事后页面确认和 v5 request/response/Header/qualified-finished 聚合为准，不再以聊天确认前 state 是否非空判失败。

L5-A2b21 未运行代码测试；它是单次 live 协议验收。结果为 connector `exit=0 / finished_target`，cycles=25、successful=24、request/response/Header=23/23/23、finished raw/qualified=2/1、four-player-unqualified=1、transport failure/timeout/diagnostics=0。v5 audit 为 449 bytes、SHA-256 `6eed257558d1ddd58239b8a5d094d3ebe209895abb5c74cd323824dd44c305d4`。该 audit 不统计模型调用，因此测试结论只覆盖 `deepseek` 模式的协议闭环，不覆盖模型实际参与或动作质量。

L5-A2b22 未运行测试、preflight 或网络。唯一最小 finished tombstone 经严格验证后删除，state 文件数 1→0；原 v5 audit 不变，新 cleanup audit 为 405 bytes、SHA-256 `10037c02ffeca2e4967aa3925e893d4386cd9df76cd213086c8ede2260079c13`。L5-A3a 的测试必须全部使用 fake client/transport，覆盖模型结果、最终来源、fallback、重放去重和 v6 audit 守恒，真实网络计数保持 0。

L5-A3a 验证通过：定向 30 项、全量 597 项、`git diff --check`。新增测试覆盖不可变快照、严格类别/整数、五类动作来源、四类模型结果、DeepSeek/adapter 两层 fallback、pending/finished 去重、v6 audit 与 malformed observability fail-closed；未新增真实网络、配置读取或敏感持久化。L5-A3b 需复跑该基线并执行一次零网络 deepseek preflight，不能直接进入 live。

L5-A3c 是单次 live 观测，不是代码测试：connector exit 0，cycles=13，request/response/Header=12/12/12，qualified finished=1，transport failure/timeout/diagnostics=0。v6 audit 为 619 bytes、SHA-256 `f29029e9b6dfe0dc8cfcf96b85e7b3a917270eaf4c6f357846d78060c8e60ac9`；Agent decision=11（local shortcut=1、model=10），model attempt/success=10/10，fallback=0。该结果验证模型路径观测契约，但不测试相对动作质量。

L5-A3d 未运行测试、preflight 或网络。唯一最小 finished tombstone 严格验证后删除，state 文件数 1→0；既有 audits 不变，新 cleanup audit 为 345 bytes、SHA-256 `a71e233af98d55000a074413b8f4cc97e564db484bf52b5c204e5758681a0225`。L5-A4a 测试必须使用 synthetic finished rows，覆盖正常 0/1/2/3 团队分数、`-2/0/1/1` 错误结果、畸形 score、qualified provenance 与 v7 audit 守恒，真实网络为 0。

L5-A4a 验证通过：定向 24 项、扩展相关 33 项、全量 604 项、`git diff --check`。测试覆盖四座位下的正常 0/1/2/3 团队结果、平台 `-2/0/1/1`、非法 score shape、仅 qualified finished 记录、重复 finished 去重、recorder 故障隔离、v7 audit 加法兼容与结果守恒；全部使用 synthetic finished rows/fake transport，真实配置/state/audit 与网络计数为 0。检查点为 `31e2fa5a474a377baa3fb80a4a427766623b96c7`。

L5-A4b 测试必须覆盖确定性 seed×seat×mode 赛程、AB/BA 平衡、严格 v7 audit 复核、缺失/重复/异常整对排除、四个 score bucket、胜负与 paired delta、seat-to-overall 和模型观测守恒、精确 Fraction、输入排列不变、canonical JSON 与隐私边界。测试只能使用合成 v7 audit，不导入或调用 transport、connector、DeepSeek client、配置或真实网络。

L5-A4b 验证通过：定向 8 项、全量 612 项、`git diff --check`。测试已覆盖严格条件/seed、确定性四座位 AB/BA 赛程、合法 v7 成对聚合、缺失/重复/未知提交、错误 mode/profile、transport/非正常结果、DeepSeek 观测守恒、零分母 Fraction、输入排列不变与敏感字段扫描。检查点为 `e1b4e14f2806b962c16a08434f8fef589bf9630b`，实现只使用标准库且真实网络为 0。

L5-A4c 不新增代码测试；离线准入必须复跑上述 8 项与全量 612 项，并验证现有 `build_paired_schedule((24001, 24002), conditions)` 精确生成 8 对、16 局、四座位各 2 对、rule/deepseek 各 8 局、AB/BA 各 4。rule/deepseek preflight 必须分别 exit 0、固定 stdout、空 stderr/state、零网络且无残留。任何门槛失败都不得进入 live 或请求部分授权。

L5-A4c 首次前置因缺少旧桌清理确认和容量根目录而在测试前停止；8/612 回归、目录探针、赛程生成和双 preflight 均未运行。该 `precondition_failed` 不是测试失败，也不改变 612 项基线。收到两项人工输入后，L5-A4c2 才执行原定验证，不能以历史结果替代。

L5-A4c 容量运行不是代码测试：第 1 局 rule 与第 2 局 deepseek 的 v7 audit 完成闭环，第 2 局聚合为 15 次 local shortcut、9 次 model success、fallback=0；第 3 局在 request=0 时产生 `poll_malformed` 并触发整批停止。前两局不得因成功而绕过缺失的其余 14 局，也不得进入新的聚合报告。

L5-A4d 不修改测试基线。恢复准入需复跑 L5-A4b 定向 8 项、全量 612 项与 diff check，并验证 `build_paired_schedule((25001, 25002), conditions)` 仍为 8 对/16 局、rule/deepseek 各 8、AB/BA 各 4。新批次前必须完成两个独立零网络 preflight；容量运行中不得并行额外测试桌或用人工观察替代 v7 audit。

L5-A4d1 已收到人工旧桌清理确认和新根目录路径，但尚未产生测试结果。实施顺序必须是目录资格/探针先于 8/612 回归，回归先于 manifest，manifest 先于两个 preflight；任何一步失败都不得使用历史 612 项或旧 preflight 结果替代。

L5-A4d1 实际复跑定向 8 项、全量 612 项和 `git diff --check` 均通过；目录探针也通过。后续 manifest 封装命令在写入前失败，因此该步骤没有生成新的赛程测试 artifact，也没有运行 preflight。L5-A4d2b 不重复测试，只在内存中断言现有生成器对 `25001/25002` 产生 8 对/16 局及 AB/BA、seat、mode 守恒，再执行一次 canonical manifest 原子写入。

L5-A4d2b 实际未进入上述内存断言：仓库外 runner 在导入 `evaluation` 时退出，容量根目录仍为 0 文件，preflight/network 为 0。L5-A4d2d 不重复 8/612；新增的前置是 module spec/origin 必须指向已核验仓库根，并在独立资格目录完成导入后才允许生成赛程和写入 manifest。

L5-A4d2d 已完成上述导入资格、内存守恒和原子写入，固定 manifest 为 3256 bytes / `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`。L5-A4d3 不重复代码测试；测试门槛改为 manifest 全量复核、16 个预注册 state/audit 布局守恒，以及 rule/deepseek 各一次 preflight 的 exit/stdout/stderr/state/零网络门槛。

L5-A4d3 的布局与 manifest 门槛通过，但旧进程检查自匹配，故两个 preflight 执行次数均为 0。L5-A4d3a 不重复代码测试或布局创建；只把进程候选限制为 `python.exe/pythonw.exe` 且具有独立 `-m integrations.botzone` 参数，再执行原定 rule/deepseek 各一次 preflight 与零网络守恒检查。

25001/25002 批次的 game 1 没有 completion audit，且人工桌进入时 connector 已退出并留下 1 个活动 state；因此 16 局容量门槛在首局失败，后续不得继续。L5-A4e1 不运行代码测试；其验收只覆盖单文件 schema/归属、其余 15 个空 state、16 个缺失 game audit、精确删除前后 `1→0`、manifest hash 不变、脱敏 cleanup audit 与零网络计数。

L5-A4e1 因 game 1 audit 实际存在而在 state 解析/删除前停止。L5-A4e2 仍不运行代码测试；只读验收覆盖 v7 schema/字段/守恒、session schema/归属、audit/state bytes-hash 前后不变、其余 15 局为空，以及四种固定关系分类。任何 malformed 或 unknown 关系都不得清理。

L5-A4e2 实际分类为 `evidence_relation_unknown`，源 audit/state bytes 与 hash 前后不变。L5-A4e3 测试必须覆盖 token 严格语法、CLI→runner→SessionStore/audit 传递、活动/重启/finished 保持、不同 token 冲突、v7/v3 默认兼容、新 audit 与 benchmark token 匹配，以及 token 不进入 Agent/transport/聚合报告；全部使用合成输入和零网络。

L5-A4e3 实际通过定向 34、兼容 35、全量 617 与 diff check。L5-A4e4 不重复代码测试；验收改为新 manifest 的 16-token 唯一性/公式/赛程守恒、路径隔离、16 个空 state/缺失 audit、rule/deepseek 各一次带 token preflight、manifest 不变及全部零网络计数。

L5-A4e4 上述门槛全部通过：manifest 3635 bytes / `f1793c…63241`，summary 653 bytes / `785ff0…d995a`，双 preflight ready 且零网络。L5-A4e5 不是代码回归；每局验收覆盖进程句柄、人工握手、exit/finished/request 守恒、零 transport/protocol 异常、v8/v4/token 三方一致和正常结果；16 局后再运行现有离线 aggregate 并要求 8/8 pairs valid。

L5-A4e5 未进入上述逐局验收：game 1 在人工建桌提示前退出，state/audit 均缺失，progress 为 `batch_invalid_before_table`，其余局未启动。没有 exit/stdout/stderr 时不得将该失败计为 transport、protocol、DeepSeek 或 run-token 测试失败。L5-A4e6 的离线测试改为锁定 launcher 对 agent/state/run-token 的严格传递、单进程流捕获、固定退出分类和 token 脱敏；不得执行 live 或复用旧 seed。

L5-A4e6 实际通过 launcher 及相关定向 32 项、全量 619 项和 diff check；检查点 `2209bb71e35c4142c28bf1218fb316f8cf67da2d` 仅含 launcher 与其测试。L5-A4e7 不新增代码回归：live 验收覆盖真实进程句柄、UI 连接/建桌、固定 stream、exit/finished/request 守恒、零 transport/protocol 异常、正常结果及 v8/v4/token 三方一致。该 pilot 不进入 paired aggregate，也不证明策略收益。

L5-A4e7 实际只产生两个 0-byte stream，state/audit/对局请求均为 0，故没有进入 live 验收并判 invalid。L5-A4e8 不新增代码测试；新增执行门槛是 launcher 启动必须返回仍运行的统一 session ID，并在 Browser 操作前后用同一 ID 证明存活。直接 exit、session 丢失或 detached 启动均在建桌前失败；成功仍需完整 v8/v4/token 与对局守恒。

L5-A4e8 未获得 session ID 并判 invalid。随后新增的零网络执行资格不是代码测试：项目 `.venv` 合成长进程在初始 yield 后返回 session ID `45404`，下一次轮询输出 completion 并 exit 0。L5-A4e9 据此直接运行 connector CLI，不运行 launcher；验收先要求 direct command 返回 session ID，再进入 Browser/对局/v8/v4/token 门槛。

首次独立 L5-A2b7 实施因任务上下文缺失 Bot ID/授权而在操作前返回 `precondition_failed`；state/audit、配置读取、connector、Botzone GET 和 DeepSeek 请求均为 0。恢复验收必须新增“敏感参与者与授权来自当前实施任务紧邻用户消息”的前置检查；仅 docs 中的状态声明不能替代该检查。

## 1. 测试入口

全部测试：

```bash
python -m unittest discover -q
```

当前全量基线：556 项通过（U0-A1 实现检查点 `085162972363e634fe224c9f1725063b3cd13686`）。

核心规则回归：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

AI 优化相关测试：

```bash
python -m unittest tests.test_hand_evaluator tests.test_card_tracker tests.test_action_pruning tests.test_opening_strategy tests.test_rag_step_h tests.test_deepseek_prompt_step_h tests.test_deepseek_step_e -q
```

## 2. 必须长期通过的测试

### 规则和接口

- 牌型识别、逢人配、王类白名单和顺子边界；
- 合法动作生成、同型和跨型压制；
- `reset()`、`observe()`、`legal_actions()`、`step(action_id)`；
- 接风、三游终局、末游、胜负和平局；
- AI 返回值始终来自当前合法动作集合。

### 本地快捷路径

- 仅有 `pass` 时不调用评分、记牌、RAG 或 DeepSeek；
- 存在一次出完动作时直接本地选择；
- 公式化开局命中时跳过 RAG 和 DeepSeek；
- H2-A1/A1a 残余结构、CLI 来源、精确公开 fixture、真实 97 分和未知 token fail-closed 已覆盖；单文件 21 项、相关 74 项、全量 371 项通过；
- 本地策略返回的 ID 必须来自原始 `legal_actions`。

### 动作剪枝

- 剪枝结果是原始合法动作的子集；
- 不合并 `carrier_cards`、逢人配声明或动作 ID 不同的动作；
- 跟牌保留 `pass`、压制动作、逢人配动作和一次出完动作；
- 提示词展示上限不能移除关键动作；
- 最终合法性校验仍针对原始合法动作集合。

### RAG

- 规则库和经验库 front matter 可解析；
- `scene / phase / hand_strength / action_context` 标签完整；
- 规则证据和经验依据分层；
- 冲突或越界条目不能进入 accepted evidence；
- 无匹配或检索异常不能破坏本地决策；
- RAG 不生成或执行动作。

## 3. Step I：阶段分类测试

新增阶段分类器后必须覆盖：

- 历史 0 和 8 个动作仍属于 `opening`；
- 历史 9 个动作进入 `midgame`；
- 自己 9 张进入 `endgame`；
- 任一其他玩家 5 张进入 `endgame`；
- 已有完赛玩家进入 `endgame`；
- 外部合计 20 张进入 `near_open_endgame`；
- 外部合计 12 张进入 `critical_endgame`；
- 临界值优先级正确；
- 开局、RAG、剪枝使用同一个阶段结果。

## 4. Step J：牌面信念测试

### J-A：公开事实层

状态：已完成。`tests/test_card_belief.py` 与兼容测试共 31 项通过，全量 141 项通过。

- 初始完整牌池为 108 张；
- 自己手牌和历史 `carrier_cards` 从未见牌池正确扣除；
- 同一点数同一花色的两副牌副本计数正确；
- 王各 2 张，普通牌每个花色各 2 张；
- 逢人配声明使用真实 `carrier_cards`，不能把声明牌当作真实已出牌；
- 旧历史缺少 `carrier_cards` 时才回退到 `declared_cards`；
- 不合法或重复历史产生诊断信息，而不是静默得到负计数。

### J-B1：所有权域与容量约束

状态：已完成。J-B1 与兼容测试共 43 项通过，全量 153 项通过。

- 只消费 J-A 的 `CardBeliefState`；
- 自己、已完赛和零容量玩家不进入外部未知牌归属域；
- token/点数归属域覆盖全部仍可持牌的外部玩家；
- 玩家公开剩余容量总和与未见牌总数一致；
- 输入不精确、容量冲突或空归属域产生诊断；
- 多个候选玩家存在时不产生 `confirmed_cards`；
- 只有硬约束唯一且输入一致时才允许确认；
- pass 次数不能缩小硬归属域。

### J-B2：有限残局分配

状态：已完成。J-B2 与兼容测试共 61 项通过，全量 171 项通过。

- 只在外部未知牌不超过 12 张、token 精确且约束一致时枚举；
- 相同 token 副本按计数分配，不重复计算副本排列；
- 每个完整解满足 token 总数、玩家容量和 J-B1 所有权域；
- 输出完整可行分配数量及逐玩家 token 数量上下界；
- 无可行解时输出诊断且不确认；
- 搜索节点或解数量达到上限时标记截断；
- 截断搜索不得输出唯一性结论；
- `confirmed` 只能来自所有完整可行解一致保证的副本。

### J-C：软推断与校准

#### J-C1：离线真值评测

状态：已完成。J-C1 与兼容测试共 78 项通过，全量 188 项通过。

- ground truth 与 J-A 未见 token multiset 不一致时拒绝评分；
- 真实持牌玩家进入 token 归属域时计为覆盖；
- 重复 token 按副本数统计确认正确数和错误数；
- 完整 J-B2 的真实持牌数必须落在对应 min/max 内；
- 截断、跳过或无解结果不得按完整上下界评分；
- 零分母指标有确定值，不产生异常或 NaN；
- 评测结果不包含或序列化真实手牌。

#### J-C2a：公开行为事件

状态：已完成。J-C2a 与兼容测试共 92 项通过，全量 202 项通过。

- 同一轮 pass 链接到此前最近一次非 pass 动作；
- 跟牌更新后，后续 pass 链接到新的桌面动作；
- 新 round 的首个非 pass 标为首出；
- 不存在前置非 pass 的孤立 pass 只产生诊断；
- 声明牌与真实 `carrier_cards` 分别保留；
- 每位玩家的 pass、首出、跟牌和牌型计数正确；
- 格式错误历史不导致异常或伪造证据；
- 输出不含可能归属、概率、置信度或确认牌。

#### J-C2b1：最小软评分与候选排序

状态：已完成。J-C2b1 与兼容测试共 107 项通过，全量 217 项通过。

- 候选 rank 只来自硬归属域；
- 完整 J-B2 可收窄候选，不完整结果回退 J-B1；
- confirmed rank 不受软负分影响；
- 对敌方 single 的有效 pass 只降低可压过该 single 的候选 rank；
- 队友 single、非 single、孤立 pass 和无效响应链接不计分；
- 重复弱信号累计但受明确下限保护；
- 每项负分都有公开事件证据；
- 同分候选属于同一 score tier；
- 评分不修改 possible owners 或 confirmed。

#### J-C2b2：Top-K 与零软分消融

状态：已完成。J-C2b2 与兼容测试共 120 项通过，全量 230 项通过。

- baseline 与 soft 使用完全相同的玩家、rank 候选和硬状态；
- baseline 将 possible 软分归零并清除 evidence；
- score tier 跨越 K 时整体进入 Top-K 选择集；
- 同分稳定顺序变化不改变评测结果；
- 统计 Top-1/Top-3 召回、精确率和实际选择规模；
- 缺失真实 rank 计为未命中，不泄露真值明细；
- 最坏位置 MRR 使用真实 rank 所在 tier 的末尾位置；
- 报告 baseline、soft 和 delta，零分母稳定无 NaN。

#### J-C3a：多种子离线残局基准

状态：已完成。J-C3a 与兼容测试共 130 项通过，全量 240 项通过。

- 固定种子和相同参数重复运行得到完全一致的聚合报告；
- 规则 AI 推进时每个动作 ID 都来自当前公开合法动作；
- 只采集 `near_open_endgame` 和 `critical_endgame`，并按统一阶段分别聚合；
- 每个 `(seed, step_no, observer_player_id)` 最多采集一次；
- 真实手牌只在 `evaluation/` 内从离线引擎状态提取；
- J-A 至 J-C2b2 使用公开 observation 构造，不能读取隐藏牌；
- 总体和分阶段指标由原始计数汇总后重算，不能直接平均样本比率；
- 最坏位置 MRR 按 `truth_rank_count` 加权；
- 报告记录游戏数、候选样本数、有效/无效/跳过数和诊断频次；
- 报告及 `to_dict()` 不包含 seed 对应手牌、逐样本 token/rank、玩家真值或其他可逆真值明细；
- 非法参数、步数上限和异常样本有确定状态，不产生 NaN；
- 不修改现有启发式，不输出置信度，不接入 RAG、DeepSeek 或策略主链。

#### J-C3b：预注册正式基准

状态：已完成。200 局双运行结果和 SHA-256 一致，8719 个样本全部有效，唯一判定为 `retain_for_policy_diverse_validation`。

- J-C3a 必须先形成可追溯 Git 提交；
- 固定 seed `1000..1199`，不得替换、筛选或删除不利种子；
- 固定 `current_level_rank="2"`、`max_steps=5000`、`max_samples_per_game=512`；
- 两次完整运行的报告和 canonical JSON SHA-256 必须一致；
- 200 局全部完成，无 invalid、sample limit skip、step limit 或其他诊断；
- 两个阶段必须各有至少 1000 个有效样本；
- candidate recall 保持 1.0，candidate recall delta 保持 0；
- Top-1/Top-3 recall 不低于 baseline；
- overall Top-1/Top-3 precision delta 至少为 0.002；
- overall worst-case MRR delta 至少为 0.001；
- 两个阶段的 precision 和 MRR delta 均大于 0；
- 结果只代表 RuleBasedAI 轨迹，不外推到战略性 pass、DeepSeek 或胜率。

#### J-C3c1：战略性 pass 策略基准载体

状态：已完成。J-C3c1 与兼容测试共 140 项通过，全量 250 项通过。

- evaluation-only 策略只读取公开 observation 和合法动作；
- 只有当前敌方 single、pass 合法且至少存在一个非 pass 合法动作时，才计为战略性 pass 机会；
- 队友领出、非 single、孤立桌面、仅 pass 或无 pass 均不计机会；
- 0% 策略与现有 RuleBasedAI 的动作轨迹和 rank 报告完全一致；
- 25%、50%、100% 策略使用稳定整数门控，固定 seed 可重复；
- 100% 策略在每个合格机会选择合法 pass；
- 未命中门控时完全回退现有 RuleBasedAI，不复制其动作排序；
- 每种策略使用独立新对局和新 agent，不共享状态；
- 报告包含策略名、机会数、主动 pass 数和聚合 rank 报告；
- 报告不包含 seed、逐样本动作、真实牌、token 或 rank 明细；
- 默认 J-C3a API 与 J-C3c1 前的 240 项基线保持兼容。

#### J-C3c2：策略分布正式验收

状态：已完成。四策略各 100 局双运行结果一致，唯一判定为 `reject_unconditioned_pass_signal`。

- J-C3c1 必须先形成可追溯提交，工作区保持干净；
- 正式 seed 与 J-C3b、J-C3c1 开发试跑完全独立；
- 四个策略使用相同 seed 和参数，并各自运行全新对局；
- 两次完整运行报告与 canonical JSON SHA-256 一致；
- 每个策略无 incomplete、invalid、sample skip 或 diagnostics；
- forced-only 必须再次满足 J-C3b 的召回和正向排序门槛；
- 所有策略 candidate recall 保持 1.0；
- 25% 战略 pass 的 Top-3 recall 回退超过 0.02 时，当前无条件 pass 信号不得进入置信度校准；
- 25% 战略 pass 通过但 50/100% 未通过时，只能进入策略条件化重设计；
- MRR 改善不能抵消 Top-K recall 护栏失败；
- 不在正式 seed 上调参或重新筛选样本。

#### J-C3d1：撤销无条件 pass 软扣分

状态：已完成。J-C3d1 与兼容测试共 140 项通过，全量 250 项通过。

- enemy single pass 不再改变任何 possible candidate 的 soft score；
- 单次、重复、不同 round 的 pass 均不生成 `opponent_single_pass` evidence；
- confirmed candidate、hard owner domain 和 J-B2 收窄结果保持不变；
- 所有 possible candidate `soft_score=0`、`evidence=()`；
- 无 confirmed 时所有 possible rank 属于同一 tier；
- 有 confirmed 时 confirmed/possible 仍分成两个 tier；
- 稳定 rank 顺序只用于序列化，不表达额外置信；
- 删除 pass penalty 参数，旧调用必须显式失败，不能静默忽略；
- `card_signals.py` 的公开 pass 事件继续保留；
- `ranking_metrics.py` 的通用 soft ranking 校验和合成消融能力继续保留；
- J-C3a/J-C3c1 基准运行器保持可用；
- 全量测试无回归。

#### J-C3d2：neutral corpus 封板

状态：已完成。四策略各 50 局双运行结果一致，12 个 bucket 全部相等，判定为 `neutral_baseline_verified`。

- J-C3d1 必须先形成可追溯提交，工作区干净；
- 固定独立 seed `3000..3049`，四种策略各 50 局；
- 两次完整报告和 canonical JSON SHA-256 一致；
- 每个策略无 incomplete、invalid、skip 或 diagnostics；
- 每个策略 near-open/critical 均至少 500 个有效样本；
- 策略机会数与主动 pass 数满足既有 rate 约束；
- 每个策略、每个阶段的 baseline 与 neutral snapshot 完全相等；
- 所有 candidate/Top-K/选择规模/MRR delta 严格为 0；
- neutral ranker 在 forced/战略 pass 策略下 soft 与 baseline 完全一致；
- 通过后判定 `neutral_baseline_verified`，否则 `benchmark_invalid`；
- 不在正式 seed 上修改实现、参数或筛选样本。

#### J-D1a：物理分配权重

状态：已完成。J-D1a 与兼容测试共 132 项通过，全量 256 项通过。

- 完整 search 的每个 count matrix 计算精确整数权重；
- token count 为 `c`、各玩家份额为 `k_i` 时，token 权重为
  `c! / product(k_i!)`；
- 一个矩阵总权重为所有 token 权重的乘积；
- 相同 token 两副本的 1/1 split 权重为 2，2/0 split 权重为 1；
- 全部 token count 为 1 时，总权重等于 feasible matrix count；
- 聚合全局物理分配权重；
- 聚合逐玩家逐 token 的持有权重和副本数加权和；
- 唯一分配、重复 token、非对称容量和受限 domain 均有精确测试；
- 所有 numerators 不超过全局分母对应的合法上界；
- complete 结果可序列化、不可变且固定输入可重复；
- truncated/skipped/invalid/no-feasible 结果的权重统计全部为空或 0；
- partial traversal 不得泄露边际信息；
- 现有 feasible count、min/max、confirmed 和 possible owners 不变；
- 不输出 float、概率、置信度或 ground truth。

#### J-D1b：rank 精确整数边际

状态：已完成。J-D1b 与兼容测试共 139 项通过，全量 263 项通过。

- token 必须映射到合法 rank，joker 保持 `SJ` / `BJ`；
- token 聚合得到的逐 rank 总数必须与 `unseen_cards_by_rank` 一致；
- 每个完整 matrix 内，逐玩家同 rank 副本数先求和；
- rank 副本数分子等于同 rank token 副本数分子之和；
- rank 持有分子按“至少持有一张”事件计一次，不能直接求和 token 持有分子；
- 覆盖一个玩家同时持有同 rank 多花色的重叠事件测试；
- 单 token rank 的 rank 持有/副本分子与 token 级结果一致；
- 所有玩家 rank 副本数分子之和等于 `rank_count * physical_assignment_count`；
- rank 持有分子位于 `[0, physical_assignment_count]`；
- complete 输出不可变、可 JSON 序列化且固定输入可重复；
- truncated/skipped/invalid/no-feasible 的 rank mapping 全部为空；
- 不改变 J-B2/J-D1a 的搜索、截断、硬域、确认或 token 边际语义；
- 不输出 float、概率、置信度，不使用 pass、策略或 ground truth。

#### J-D1c1：单样本概率评分

状态：已完成。J-D1c1 与兼容测试共 152 项通过，全量 276 项通过。

- 只接受完整、有解、物理分母为正且 phase 一致的 J-D1b；
- 严格校验 allocation 玩家、容量、rank key、整数边际和跨玩家副本守恒；
- ground truth 只允许在 `evaluation/` 显式传入，并与公开 token multiset 完全一致；
- 每个活跃外部玩家 × 每个正数未见 rank 构成一个持有事件；
- Brier 平方误差使用精确有理数累计；
- rank 副本期望的平方误差使用精确有理数累计；
- 固定 10 个概率桶，使用整数算术确定桶边界；
- 每个桶只保留样本数、预测概率和的分子/分母、真实正例数；
- 报告不包含玩家-rank 真值明细、真实 token、真实 rank 列表或手牌；
- invalid/truncated/skipped/no-feasible 结果返回零化无效报告；
- 报告不可变、JSON 友好、无 NaN/Infinity，固定输入可重复；
- pass 只作为公开行为事实，不作为默认持牌负证据。

#### J-D1c2a：多样本精确聚合

状态：已完成。J-D1c2a 与兼容测试共 166 项通过，全量 290 项通过。

- valid 样本按 rank pair 数做微聚合，不平均单样本分数；
- 不同分母的 Brier 和 copy 误差使用 `Fraction` 精确相加；
- Brier mean 与 copy MSE 从总误差和除以总 pair 数重算；
- ECE 使用 `sum(abs(prediction_sum - truth_positive)) / total_pair_count`；
- MCE 使用非空桶平均预测与真实率的最大绝对差；
- 确定性错误率和真实正例率输出精确分数；
- 十档桶跨样本精确聚合，空桶保持 `0/1`；
- invalid 样本不进入指标，只进入 invalid count 与规范化 diagnostics；
- 同一无效样本内重复诊断类别只计一次；
- 聚合结果不保留单样本报告、seed、玩家、rank、token 或手牌；
- 冻结、不可变、JSON 友好且固定输入顺序无关；
- malformed 手工报告必须显式拒绝，不能静默产生指标。

#### J-D1c2b：固定种子采集与开发容量

- 状态：已完成。定向 179 项、全量 303 项通过；开发判定 `development_capacity_verified`；
- 默认只采集 `critical_endgame`，因为精确分配默认上限为 12 张；
- 按 overall 和外部未知牌 `0..4`、`5..8`、`9..12` 聚合；
- 固定 seed、级牌、步数、样本上限和搜索上限；
- 同一参数双运行报告和 canonical JSON hash 一致；
- 每个游戏/玩家只构造一次 agent，所有动作经过合法 action ID 校验；
- 真值只在公开推断完成后由既有 evaluation-only helper 提取；
- 报告不保留 seed、逐样本报告、observation、玩家或真值明细；
- 重复样本、步数上限和样本上限有规范化 diagnostics；
- overall 必须由原始单样本报告合并，不平均分桶指标；
- 外部牌数桶互斥且完整覆盖所有 evaluated 样本；
- 开发 seed 只用于容量和运行成本，不据此宣称校准通过；
- 正式参数与门槛留给 J-D1c2c 预注册；
- 由原始充分统计量重算 Brier 与可靠性，不平均单样本比例；
- 不在正式 seed 上调桶、调参或筛选样本。

#### J-D1c2c：独立语料正式校准

状态：已完成。16 项完整性与全部校准护栏通过，判定 `retain_for_policy_diverse_calibration`。

- HEAD 必须包含 J-D1c2b，运行前后工作区均干净；
- seed `5000..5099`，默认规则 AI，完整运行两次；
- 两份报告、`to_dict()` 和 canonical JSON SHA-256 完全相同；
- 100/100 局完成，无 incomplete、invalid、skip 或 diagnostics；
- eligible、evaluated、valid 三者相等；
- 三个外部牌数桶各至少 700 个 valid 样本；
- overall 与每个桶 certainty error count 均为 0；
- overall ECE 不超过 `0.03`，每个桶 ECE 不超过 `0.05`；
- overall Brier skill 相对经验正例率常数基线至少 `0.15`；
- 每个外部牌数桶 Brier skill 至少 `0.10`；
- overall 中 prediction count 至少 200 的桶，其最大 absolute gap 不超过 `0.10`；
- 每个外部牌数桶中 prediction count 至少 100 的桶，其最大 absolute gap 不超过 `0.15`；
- overall 和每个外部牌数桶至少有两个达到对应支持度的校准桶；
- 原始 MCE 与 copy MSE 只报告，不单独作为拒绝门槛；
- 正式运行中不改实现、seed、上限、分桶、支持度或阈值。

正式结果：

- 双运行 SHA-256：`c4a91d81bed216e919189fe4fdddf76c76ee8e35eb28f5fcae21ebc9e401e190`；
- 100/100 局，2727 个样本全部有效；
- 三桶样本 902 / 901 / 924；
- overall Brier skill 约 0.236809、ECE 约 0.021901、supported MCE 约 0.063909；
- overall 与三桶 certainty error 均为 0。

#### J-D1c3a：策略分布 marginal corpus

状态：已完成。定向 187 项、全量 311 项通过；开发判定 `policy_diversity_capacity_verified`。

- 固定策略顺序为 forced-only、strategic-pass 25/50/100；
- 每个策略创建独立游戏、agent 和报告；
- rate 0 corpus 与默认 marginal corpus 完全一致；
- opportunity/pass 满足 `0 <= pass <= opportunity`；
- rate 0 主动 pass 为 0，rate 100 主动 pass 等于机会数；
- 每个策略报告完整对局、样本、外部牌数桶和校准指标；
- 同参数双运行报告和 hash 一致；
- 报告不包含 seed、逐样本、observation 或 truth；
- 开发试跑只验证容量与行为分布，不形成正式校准或 runtime 结论。

开发结果：

- 双运行 SHA-256：`dc5bfa083d686e57cb711e9892738713904da96178988931deda7318427a58a3`；
- 四策略各 10/10 局完成，无 invalid、skip 或 diagnostics；
- opportunity/pass 为 117/0、121/48、127/63、133/133；
- 四策略均覆盖三个 external bucket。

#### J-D1c3b：多策略正式校准

状态：已完成，唯一判定 `benchmark_invalid`。运行中未修改代码、测试、docs、策略、参数、分桶或阈值。

- HEAD 必须包含 J-D1c3a，运行前后工作区干净；
- seed `7000..7049`，四策略各 50 局，完整运行两次；
- 两份顶层报告和 canonical JSON SHA-256 完全一致；
- 每个策略 50/50 局完成，无 invalid、skip 或 diagnostics；
- 每个策略的三个 external bucket 各至少 350 个 valid 样本；
- forced 主动 pass 为 0，100% 主动 pass 等于机会数；
- 25/50% 均有主动 pass，实际比例满足 `rate25 < rate50 < rate100`；
- 每个策略的 overall 与三桶 certainty error 均为 0；
- 每个策略 overall ECE ≤ 0.03，每个 external bucket ECE ≤ 0.05；
- 每个策略 overall Brier skill ≥ 0.15，每个 external bucket skill ≥ 0.10；
- overall 中 count≥200 的支持桶 MCE ≤0.10；external 桶中 count≥100 的支持桶 MCE ≤0.15；
- 每个策略、每个聚合范围至少两个 calibration bin 达到对应支持度；
- 不计算跨策略平均指标，不用其他策略通过抵消单策略失败。

正式结果：

- 双运行耗时约 322.8s / 321.9s，报告完全相等；
- SHA-256 均为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 定向 187 项、全量 311 项测试通过；
- 四策略各 50/50 局完成，无 invalid、skip 或 diagnostics；
- 每个策略的三个 external bucket 均至少 350 个有效样本；
- 行为边界、行为比例梯度、样本守恒和双运行确定性全部通过；
- `strategic_pass_100 / external_0_4` 有 436 个有效样本和 1201 个 rank pair；
- 该范围 prediction count 为 `[0, 0, 60, 25, 0, 40, 26, 36, 2, 1012]`，只有 bin 9 达到 count>=100；
- 其余 15 个范围通过全部数值与支持度护栏，但不能抵消该失败。

#### J-D1c3b2：支持度扩容复验

状态：已完成，判定 `policy_diverse_calibration_verified`。运行中未修改实现、测试、docs、策略、分桶、支持阈值或数值护栏。

- seed `8000..8119`，四策略各 120 局，完整运行两次；
- seed `7000..7049` 只用于样本量规划，不进入新报告或判定；
- 运行前后工作区必须干净；
- 定向 187 项、全量 311 项测试和 `git diff --check` 必须通过；
- 两次报告、`to_dict()` 和 canonical JSON SHA-256 必须完全一致；
- 每个策略 120/120 局完成，无 incomplete、invalid、skip 或 diagnostics；
- 每个策略三个 external bucket 各至少 800 个 valid 样本；
- 策略行为边界和实际主动 pass 比例严格递增；
- certainty、ECE、Brier skill、supported MCE 门槛与 J-D1c3b 完全相同；
- overall 仍以 count>=200、external 仍以 count>=100 定义支持 bin；
- 每个策略、每个聚合范围仍至少需要两个支持 bin；
- 任一完整性或支持度失败判定 `benchmark_invalid`；有效 benchmark 的任一数值护栏失败判定 `reject_runtime_confidence`；全部通过才判定 `policy_diverse_calibration_verified`。

正式结果：

- 双运行耗时约 790.2s / 785.0s，报告完全相等；
- SHA-256 均为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 定向 187 项、全量 311 项测试通过；
- 四策略各 120/120 局完成，无 invalid、skip 或 diagnostics；
- 有效样本为 3260 / 3399 / 3531 / 2997；
- 每个策略的三个 external bucket 均至少 984 个有效样本；
- 主动 pass 比例为 0、约 0.357、约 0.546、1.0；
- 16 个范围支持 bin 数均至少为 4；
- 16 个范围全部通过 certainty、ECE、Brier skill 和 supported MCE 护栏。

#### J-D1c3c1：runtime confidence 数据契约

状态：已完成；J-D1c3c1a 已补齐 malformed 边界。未接入任何决策消费者。

- available 只允许 `critical_endgame`、精确牌池、精确一致约束和完整有解 allocation；
- `physical_assignment_count` 必须为非 `bool` 正整数；
- belief、constraints、allocation 的 phase、外部牌数、玩家集合和容量必须一致；
- rank key 必须与正数 `unseen_cards_by_rank` 完全一致；
- presence 分子必须位于 `[0, denominator]`；
- copy 分子必须满足逐玩家范围与跨玩家 `rank_count * denominator` 守恒；
- 输出只使用整数分子/分母，`to_dict()` 可 JSON 序列化；
- certainty 只允许 `presence_numerator == denominator`；
- 阶段外、不精确、不一致、截断、无解、跳过、诊断或 malformed 手工夹具都整体 unavailable；
- unavailable 状态必须零分母、无玩家结果，不泄露部分边际；
- frozen/slots、稳定顺序和不可变结构必须有测试；
- `agents/card_confidence.py` 不得导入 `evaluation/`，也不得读取 observation、history 或 ground truth；
- `deepseek_ai.py`、`deepseek_client.py`、RAG、CLI、剪枝和动作选择在本步骤保持不变；
- 先运行 `tests.test_card_confidence` 及 J-A/J-B/J-D1 allocation 相关定向测试，再运行全量 `python -m unittest discover -q`。

J-D1c3c1a 已补测：

- exact/consistent/search-complete 字段为 `1`、字符串或其他 truthy 非布尔值；
- constraints 中存在公开 active external 集合之外的额外玩家；
- copy mapping 值为字符串、`None`、float 或 `bool` 时不得在守恒求和中抛异常。

#### J-D1c3c1a：fail-closed 边界封板

状态：已完成。只修改 `agents/card_confidence.py` 与 `tests/test_card_confidence.py`。

- `token_pool_exact`、`token_constraints_exact`、`is_consistent`、`search_complete` 必须用严格布尔检查；
- truthy 非布尔值必须 unavailable 并输出对应既有诊断；
- 额外、重复、不可哈希或缺失的 constraint/allocation 玩家必须 `player_set_mismatch`；
- copy 原始值在进入加法前必须验证为非 `bool` 非负整数；
- 字符串、`None`、float、`bool`、负数和越界 copy 均返回 `invalid_copy_numerator`；
- 非法 copy mapping 不得抛 `TypeError`，不得输出部分 players；
- copy 守恒只基于全部通过类型/范围校验的规范化整数；
- 合法输入的 `to_dict()` snapshot 与 J-D1c3c1 保持一致；
- 定向和全量回归通过，decision path 仍无 `card_confidence` 引用。

验证结果：单文件 11 项、相关 80 项、全量 322 项通过；`git diff --check` 与边界扫描通过；合法 available snapshot 不变。

#### J-D1c3c2a：runtime confidence shadow 装配

状态：已完成。只建立 orchestration 与审计，prompt 或动作未消费。

- pipeline 使用调用方传入的统一 `GamePhaseContext`，不得重复分类阶段；
- 非 critical 阶段不调用 allocation 枚举；
- critical 阶段按 J-A -> J-B1 -> J-D1b -> confidence 顺序各调用一次；
- 任一层异常转为规范 unavailable，不向 agent 抛出；
- agent 开关默认 `False`，关闭时不得调用 pipeline；
- 每次 `select_action()` 开始将 `last_card_confidence` 清空，避免跨步复用陈旧状态；
- local only-pass、一次出完和 opening shortcut 不调用 pipeline；
- shadow 开启只写审计字段，不改变 prune、RAG、prompt builder、client 参数或合法动作校验；
- 固定 observation、legal actions 和 client 返回下，shadow off/on action ID 与 decision source 相同；
- pipeline unavailable 或内部异常时，原 DeepSeek/fallback 行为保持不变；
- 不修改 `config.py`、`.env.example`、CLI 或 AppConfig；
- 全量回归和 `git diff --check` 必须通过。

验证结果：定向 40 项、相关 124 项、全量 331 项通过；off/on client 参数、动作、fallback 与 decision source 一致；边界扫描和 `git diff --check` 通过。

#### J-D1c3c2b1：confidence prompt 序列化

状态：已完成。只新增 formatter 和测试，DeepSeekClient、agent 或动作路径未修改。

- unavailable 或 source/scope 不符时返回 omitted payload；
- available 的 denominator 和全部分子必须再次验证为非 `bool` 合法整数；
- presence 和 expected-copy 分数分别用 `gcd` 约分；
- 0 输出 `0`，等于 1 输出 `1`，其他输出 `n/d`；
- 不输出 float、百分比或置信度等级；
- 所有玩家和 rank 按输入已封板顺序稳定输出；
- 文本包含“公开硬约束组合边际、不是隐藏牌事实”的边界说明；
- 固定最大字符数；超限整体 omitted 且文本为空，不允许部分截断；
- malformed 玩家、rank、分母、分子或重复项整体 omitted；
- payload frozen/slots、JSON 友好且调用稳定；
- formatter 不读取 observation/history、ground truth、evaluation 或 engine；
- 现有 DeepSeek prompt snapshot 和 action path 必须完全不变。

验证结果：formatter/confidence 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项通过；`git diff --check` 与边界扫描通过。

#### J-D1c3c2b2：默认关闭的 confidence prompt 消费

状态：已完成。只修改 agent、client 与对应测试，配置、RAG、剪枝和 engine 未修改。

- `card_confidence_prompt_enabled` 默认 False；prompt=True 且 shadow=False 时构造失败；
- 每次决策同时重置 confidence state 与 prompt payload 审计字段；
- shadow-only 不调用 formatter，client kwargs 与 J-D1c3c2a 完全一致；
- prompt 模式只格式化本步 `last_card_confidence`；
- ready 时 client kwargs 只新增一个类型化 payload；
- omitted/unavailable 时不传新 keyword，prompt 与 shadow-only 完全一致；
- `_build_structured_prompt()` 默认参数为 None，所有旧调用 snapshot 逐字不变；
- ready payload 新增且只新增一个 `【残局牌面信念】` 章节；
- client 必须复核 payload status/source/scope/diagnostics/char_count/预算；malformed payload 整体省略；
- 新章节位于 `【记牌信息】` 后、`【场景标签】` 前；
- section 文本不得二次改写、截断或重新计算概率；
- legal actions、剪枝、RAG、输出格式、fallback 和 decision source 保持不变；
- local shortcuts 不计算 state 或 payload；
- 不修改 AppConfig、环境变量、CLI 或默认运行行为；
- 定向、相关和全量测试以及 `git diff --check` 必须通过。

验证结果：confidence/pipeline/DeepSeek 定向 54 项、RAG/剪枝/开局/DeepSeek 相关 48 项、全量 345 项通过；禁止引用扫描和 `git diff --check` 通过。

#### J-D1c3c2c1：配对 prompt 覆盖与成本开发基准

状态：已完成。只新增 evaluation collector 与测试，runtime 未修改。

- 使用公开 game observation、legal actions 和统一 phase；
- 只采集 `critical_endgame`，按 external 0..4、5..8、9..12 分桶；
- 复用 0/25/50/100 strategic-pass evaluation agent，四策略对局隔离；
- 每个样本只运行一次 runtime confidence pipeline 和 formatter；
- off/on 共用相同 my_info、current_round、other_players、history、pruned actions 和 phase；
- 不调用 `suggest_action_id()`、HTTP transport 或真实 DeepSeek；
- confidence available/unavailable 与 payload ready/omitted 计数守恒；
- ready 时 on prompt 必须等于向 off prompt单次插入固定章节；
- omitted 时 on prompt 必须与 off prompt 完全相同；
- 记录 payload char 和 prompt delta 的 sum/min/max，不平均单样本均值；
- diagnostics 按冒号前类别聚合，同一样本同类只计一次；
- 报告 frozen/slots、mapping 不可变且 JSON 友好；
- 报告不含 seed、样本 ID、observation、prompt、手牌或玩家明细；
- 同参数双运行报告与 canonical JSON hash 必须一致；
- 开发试验只验证容量和覆盖，不形成动作质量或胜率结论。

验证结果：collector/formatter/pipeline 28 项、DeepSeek/策略/RAG/剪枝 77 项、全量 351 项通过；边界扫描和 `git diff --check` 通过。

开发双运行：seed `80..89`，四策略各 10 局；报告完全一致，SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；1084 个样本全部 ready，零 omitted/mismatch/diagnostics；判定 `confidence_prompt_coverage_capacity_verified`。

#### J-D1c3c2c2：独立正式 prompt coverage

状态：已完成但无效。唯一判定 `benchmark_invalid`；不是 coverage 数值失败，而是完整聚合证据未留存。

- HEAD `bc689a37f462672033d754cce7060897d70c7612`；运行前后工作区干净；
- 提交前后定向 28 项、相关 77 项、全量 351 项通过，`git diff --check` 通过；
- seed `10000..10049`，四策略各 50 局，完整运行两次；
- 两次耗时 344.621s / 342.153s；
- 两份 report、`to_dict()`、canonical JSON 完全一致，SHA-256 均为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- 边界扫描未发现网络、DeepSeek、ground truth 或 `game._state`；
- 工具层截断 stdout，未保留 4 策略 x 4 范围的完整数据；
- 按预注册约束未第三次运行、补采或改参；局部 `strategic_pass_50` 输出不参与正式通过判定。

#### J-D1c3c2c2a：可持久化恢复验收

状态：已完成。唯一判定 `confidence_prompt_coverage_verified`。

- HEAD `6b62156a98cfb97dd11e30df5f95a62dba99accd`，实现检查点 `bc689a37f462672033d754cce7060897d70c7612`；
- 仓库外审计目录为 `C:\Users\86166\AppData\Local\Temp\guandan-confidence-prompt-jd1c3c2c2a-6b62156a98cf`，runner SHA-256 为 `61ac8e55fdc57e58ee09a6af80972f1dea67bcfddd413a0f02ecb29ce6b76202`；
- 运行前后工作区干净；定向 28 项、相关 77 项、全量 351 项和 `git diff --check` 全部通过；
- seed `11000..11049`，四策略各 50 局，完整运行两次；
- 两次耗时 321.921s / 321.047s；
- 两份 JSON 均为 9218 bytes，逐字节与 canonical SHA-256 完全一致：`679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- recovered 审计摘要为 19833 bytes，SHA-256 为 `fc8e9f3d7aa016e4772350834039b4780eccf3d9330c5315eae77c9c8eac33d7`；
- 四策略 games 均为 50/50/0，样本分别为 1380 / 1469 / 1510 / 1374；
- 各策略 external 0-4 / 5-8 / 9-12 样本为 461/443/476、489/490/490、475/530/505、473/444/457；
- 5733 个样本全部 available=ready=exact insertion，零 invalid/skipped/diagnostics/unavailable/omitted/budget omitted/pair mismatch；
- 16 个范围 payload 最大 683，全部低于 2400；delta sum/min/max 精确满足每样本 +11；
- forced/25/50/100 主动 pass 为 0/498、196/547、318/557、609/609，比例严格递增；
- 原始摘要曾把 canonical JSON 键顺序误当调用顺序；只读恢复解析器按策略名/rate 复核原文件，未重跑或改 corpus；
- 未调用 DeepSeek、网络、ground truth 或 `game._state`。

字符成本 `payload sum/min/max -> prompt delta sum/min/max`：

| 策略 | overall | external_0_4 | external_5_8 | external_9_12 |
|---|---|---|---|---|
| forced | 447781/106/683 -> 462961/117/694 | 75258/106/296 -> 80329/117/307 | 143478/139/476 -> 148351/150/487 | 229045/162/683 -> 234281/173/694 |
| pass-25 | 462156/106/677 -> 478315/117/688 | 78728/106/296 -> 84107/117/307 | 153981/139/476 -> 159371/150/487 | 229447/161/677 -> 234837/172/688 |
| pass-50 | 475768/106/639 -> 492378/117/650 | 73658/106/296 -> 78883/117/307 | 165464/139/476 -> 171294/150/487 | 236646/162/639 -> 242201/173/650 |
| pass-100 | 371715/106/662 -> 386829/117/673 | 64873/106/296 -> 70076/117/307 | 111541/128/482 -> 116425/139/493 | 195301/161/662 -> 200328/172/673 |

#### J-D1c3c2c3a：无网络成对动作消融载体

状态：已完成。唯一开发判定 `confidence_action_ablation_harness_verified`。

- 只新增 `evaluation/confidence_action_ablation.py` 和对应测试；
- 单文件 6 项、相关 76 项、全量 357 项通过，`git diff --check` 通过；
- provider 显式注入，无默认 client、配置、环境或网络读取；
- critical/public-only、SHA-256 固定样本、shortcut 排除、off/on 唯一差异、AB/BA 平衡和 fail-closed 分类均已覆盖；
- 报告 frozen/slots、不可变、JSON 友好且只含聚合数据；
- 边界扫描未发现 runtime 反向导入、配置、`.env`、API key、网络、ground truth 或 `game._state`。

开发双运行：seed `120..129`、四策略、每桶 4 个样本：

- 两次耗时 39.795s / 40.446s；
- report、`to_dict()` 完全相等，canonical SHA-256 为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 四策略均 10/10/0 games、零 diagnostics；
- 每策略 12 selected/both-valid，三个桶各 4，AB/BA 各 2；
- 每轮 off/on 各 48 次，异常、malformed、no-action、错误类型、outside legal/prompt 均为 0；
- 每策略 same=0、changed=12；该结果由假 provider 首/末候选规则刻意构造，只验证载体；
- off pass 分别为 7/9/11/9，on pass 与双方 pressure 均为 0。

#### J-D1c3c2c3b：真实 DeepSeek 响应安全 live pilot

状态：已完成。唯一判定 `retain_for_action_quality_evaluation`。

- c3a 检查点 `e0065c6a3da70b3d4ded4b394817bfab3351c113`；
- 运行前后工作区干净，回归 6 / 76 / 357 项与 `git diff --check` 通过；
- endpoint/model 为 `https://api.deepseek.com` / `deepseek-v4-pro`，timeout=60、max retries=0；
- seed `13000..13009` 四策略每桶 2 样本，共 24 pair / 48 logical/physical requests；
- 总耗时 1411.005 秒，ledger 1..48 连续，off/on 各 24；
- off 延迟 sum/min/max 为 588053/7543/54488ms；on 为 807020/11651/76913ms；
- 四策略均 10/10/0、零 diagnostics，每桶 selected=2、off-first/on-first 各 1；
- forced/25/50/100 三桶 qualified 分别为 27/32/33、37/38/39、43/47/39、61/51/51；
- 48 响应全部 valid，24 pair 全部 both-valid，所有异常、解析和候选边界失败为 0；
- forced/25/50/100 same/changed 为 2/4、3/3、4/2、4/2；总计 13/11；
- off/on pass 均为 6，pressure 均为 0；
- 未持久化 key、prompt、action ID、reasoning、响应正文、样本身份或 ground truth；
- 未运行完整 DeepSeek 对局，changed 不构成 confidence 因果或质量结论。

证据 bytes / SHA-256：

- runner：14966 / `be12c6fc3e265704dab0f2be7b556aeff947f3a7bccae209540b428ce3716167`；
- ledger：8269 / `a45517e6948bf421a8af28f6f4e4a3c8bc0cddf7a925c359df9bab38c3c32753`；
- report：19501 / `02e3fe45a983e89d2982a4acba12fc437f70ee30914957096b9385caf09c756c`；
- summary：24318 / `f338f5cefdfec254482a5a4af803d507d31670f9a3f3bfbb64dd9095ffb55963`。

overall prompt-pair digests：forced `c45e7241a3c37066065c49e3c73d4b33a93d5b7b118126716446485c5af29e14`；25% `c0fb9250103869486ac0bd55689b85b0e82d37339183aa5140a7a080cf280d82`；50% `5b384f566871d2e7472584ce9499e582ace2070d94d54f54ce34b79bcf4fc800`；100% `a95d09fd98c0e72f74fdfc18a7e82aa1998c51460dfa2c0c76b6d7a9d02d17f8`。

#### J-D1c3c2c3c1：确定性分支续局质量载体

状态：已完成。唯一开发判定 `confidence_action_quality_harness_verified`。

- 只新增 `evaluation/confidence_action_quality.py` 和对应测试，未修改 c3a；
- 新模块 5 项、相关 81 项、全量 362 项通过，`git diff --check` 通过；
- c3a 原开发 canonical SHA-256 仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- clone 公开等价、状态独立、same 单分支复用、changed 双分支和 RuleBased 公开接口续局均已覆盖；
- terminal 三游补末游、非法 finish order、win/draw/loss 和 placement 字典序均已覆盖；
- 报告 frozen/slots、不可变、JSON 友好，不含 seed、样本 ID、observation、prompt、action ID、手牌、clone 或逐分支结果；
- 边界扫描未发现网络、配置、ground truth、`game._state` 或 runtime 反向导入。

开发双运行：seed `140..149`、四策略、每桶 2 个样本、`max_rollout_steps=5000`：

- 两次耗时 27.158s / 27.252s；
- report、`to_dict()` 和 canonical JSON 完全相等，SHA-256 为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`；
- 每策略三个桶各 selected=2，全部 24 pair both-valid、quality-evaluable；
- same/changed = 0/24，共 48 个分支全部 complete，零 diagnostics；
- forced/25/50/100 的 on-better/off-better/tie 为 1/1/4、1/0/5、0/0/6、1/0/5；
- 结果来自确定性假 provider，只验证质量载体，不形成真实模型动作质量或胜率结论。

#### J-D1c3c2c3c2：真实模型动作质量验收

状态：正式运行未完成。唯一判定 `quality_benchmark_invalid`。

- c3c1 checkpoint `ad85662a47f126991e8ebe0360dc0c6c4a2f1be6`；
- seed `15000..15009`，endpoint/model 为 `https://api.deepseek.com` / `deepseek-v4-pro`，timeout=60、retries=0、请求上限 48；
- 外层执行器在 30 分钟中断，仍运行的子进程随后终止，没有恢复、补采或重跑；
- ledger 连续 45 条，off/on=23/22，全部 returned 且为严格整数；
- 未达到 48 请求、24 pair 和完整 report 门槛，不报告 same/changed、rollout 或质量结果；
- 本地 5 / 81 / 362 项测试、`git diff --check` 和工作区检查通过；
- 未保存密钥、prompt、action ID、reasoning 或响应正文。

失败证据：

- runner：12718 bytes / `ffcc5448ea7ff5b960c58869db0c1e6d34f8eac621de425a11f56332ac4bb7a6`；
- ledger：9576 bytes / `908fbd2e05f2c1d85e3092c4f72054ccdd810ff2c669324c15d0cf516a9d08ab`；
- failure summary：1190 bytes / `4475786a589534b77ef8421f8f614753d1be7f9665e175312bae6396464af250`。

#### J-D1c3c2c3c2a：耐久后台恢复验收

状态：已完成。唯一判定 `quality_recovery_invalid`。

- run ID `6999cb8cde244f0c96a95601c504062f`，PID 8728 正常退出，耗时 1890.133 秒；
- ledger 1..48 连续，off/on=24/24，全部 returned；
- 四策略均 10/10/0，每策略每桶 selected=2，24 pair 全部 both-valid；
- provider 全部 valid，所有 rollout complete，diagnostics 为空；
- 正式 summary 因 canonical JSON 键顺序检查错误令 `integrity_pass=false`；
- 未重写 summary/completion、未重跑、未形成质量结论；
- 回归 5 / 81 / 362 项、兼容 hash、`git diff --check` 和工作区检查通过。

证据 hashes：

- runner `c020860c67c2663c9ed87adda974774697c396d186b82c4f7547bbccebc33a5c`；
- state `4a4ff3d487f3257fbc7d0a82392c04d3c9f5df9cabb667fa534a2be5359c2adc`；
- heartbeat `33bba4c0a966dd88e0e9c1293dc783be346cba0c65e5744acb8de28269d3d6e3`；
- ledger `c60f5d35d9ee907efd926c7e3f03ba5fdb918c463892da3f1abab6a6c2ee49df`；
- report `57df2cd1826f3e5226ab66cf2a7590f7158ec88c4843e0f7839672b3f3bb090f`；
- summary `9d9522155bea9d3c0dc24d40c33d6b0f3872d4e5ed75c8788a8d154cc0f1a2ab`；
- completion `cfed3329699e822a84313c0e92b0c3a1dbec2dd08956f3ae0e126d9fea0b25c6`；
- explicit-mapping addendum `52bab7e2de283b48d76839be4926fd75597d66046078512d8c04c94c9c5d3229`。

#### J-D1c3c2c3c2b：只读恢复审计

状态：已完成。唯一判定 `no_observed_action_quality_gain`。

- 原 c3c2a 文件前后 hashes 完全不变；
- 原 summary 唯一 false path 为派生 `integrity_pass`，原子原因仅为 canonical JSON 键序误用；
- 固定策略 lookup、内部 rate、主动 pass 比例和 48 条 ledger 独立复核通过；
- 24 pair、33 rollout branches、三桶、四策略和 quality 计数全部守恒；
- run1/run2 各 19096 bytes 且逐字节相同；
- overall same/changed=15/9，on/off better=0/0，tie=24；
- off/on team win=10/10；
- 恢复输出敏感内容扫描无匹配，未联网或调用模型。

恢复输出：

- verifier：13213 bytes / `27a82023…f774799c`；
- run1/run2：`f619c3e1…c9d83f02`；
- manifest：1062 bytes / `7d777803…6d92ad98`。

#### K-A1：策略意图路由契约

状态：K-A1/A1a 已完成并严格封板。唯一判定 `strategy_router_hardening_verified`；不接入动作选择。

- 单元测试覆盖统一 phase 复用、team/opponent 关系、hand count、immediate finish、弱牌和 malformed 输入；
- 固定优先级输出 `run_out`、`block_opponent`、`support_teammate`、`control`；
- 只用当前 round 的公开历史重建最后一个非 pass 领牌者，验证其与 table action 一致；pass 不进入持牌推断；
- 固定 fixture 覆盖联网单局第 2 轮队友领牌、第 16 轮危险对手领牌和第 20 轮自由首出阻断；
- K-A1a 深层校验 phase、五个计数字段、`other_hand_counts` 的 tuple/长度/元素类型和完赛人数边界；
- `bool`、字符串等 truthy 值不能通过整数契约；上游容器不可读时只返回可确定诊断；
- 多个可安全判定的独立错误按 `_DIAGNOSTIC_ORDER` 去重聚合，unavailable 不保留任何部分玩家、领牌或意图字段；
- 三个合法公开 fixture 有完整 `to_dict()` 快照，第 2/16/20 轮意图与 reason code 保持不变；
- K-A1a 定向 18 项、相关 86 项、全量 389 项通过；`git diff --check` 通过（仅换行符提示）；
- opening 与无效输入 fail-closed，不重复阶段分类；
- 输出 frozen/slots、不可变、JSON 友好且不含隐藏状态；
- 不修改 legal actions，不调用 DeepSeek/RAG/confidence，不读取 engine 内部状态；
- 封板只授权 K-A2a 默认关闭的 shadow 装配，不声明策略收益。

#### K-A2a：策略意图 shadow 装配

状态：已完成并验证。唯一判定 `strategy_router_shadow_verified`。

- 开关默认关闭且严格接受 `bool`，非 bool 初始化即拒绝；
- 每次决策重置 shadow 审计字段；仅 pass、一次出完和公式命中均跳过 router 与 shadow-only 评分；
- 普通模型路径只计算一次 phase，只调用一次 router，传入原始 legal actions 并复用已有手牌评估；
- router available/unavailable 只写审计字段；router 或 shadow-only 评分异常不影响模型调用和 fallback；
- off/on 的 client kwargs、结构化 prompt、动作、fallback 与 decision source 完全一致；
- `deepseek_client.py`、RAG、CLI、engine、config 与 evaluation 消费扫描无匹配；
- 定向 25 项、相关 100 项、全量 396 项通过；`git diff --check` 通过（仅换行符提示）。

#### K-A2b1：离线路由分布载体

状态：核心载体与开发容量试验已完成；本节记录 K-A2b1 当时的 `strategy_router_distribution_harness_invalid`，缺口已由 K-A2b1a 封板。

- 四种 strategic-pass 策略使用独立对局、agent 和聚合状态；
- 只消费公开 observation、原始 legal actions、统一 phase 和手牌评估；
- 按四个非 opening 阶段聚合 available/unavailable/invalid、intent、reason、领牌关系和 diagnostics；
- opening、only-pass、一次出完、重复和样本上限单独计数，各层守恒；
- seed `200..209` 双运行完全相等，SHA-256 为 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb`；
- 四策略均 10/10/0，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 主动 pass 为 `0/122`、`49/136`、`76/143`、`142/142`，比例严格递增；
- 单模块 8 项、相关 58 项、全量 404 项通过；边界扫描与 `git diff --check` 通过。

K-A2b1 当时尚未覆盖的严格反例：

- wrong source 的 available context 仍被计为 available；
- context phase 与当前 bucket phase 不同时仍被计入该 bucket；
- unknown reason 或 reason-intent 错配仍被计入 reason 分布；
- unavailable 结果缺少 source/phase/非空 diagnostics/中性字段复核。

#### K-A2b1a：router 输出 fail-closed 封板

状态：已完成，唯一判定 `strategy_router_distribution_hardening_verified`。

- available 必须具有固定 source、与 bucket 一致的 phase、空 diagnostics、单一已知 reason 与合法 reason-intent 映射；
- unavailable 必须保持全部策略字段中性，且带非空、规范字符串 diagnostics；
- malformed result 统一记为 `invalid_router_result`，不泄露或聚合伪 diagnostics；
- 合法语料的报告、`to_dict()` 和 canonical SHA-256 必须与 K-A2b1 完全一致；
- wrong source/phase/status、非 tuple、bool 冒充、未知或错配 reason、relation/leader 矛盾和 unavailable 字段泄露均已覆盖；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- seed `200..209` 双运行报告完全相等，canonical SHA-256 仍为 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb`；
- K-A2b2 只运行独立正式语料，不修改实现或阈值。

#### K-A2b2：独立语料正式覆盖验收

状态：已完成，唯一判定 `strategy_router_coverage_insufficient`。

- seed `16000..16099`、四策略各 100 局，双运行报告与 canonical JSON 完全一致；
- canonical SHA-256：`e77e5632b4b71f4a12fc1b213be78b413c70486f60e06e3f5cd35c941aa2d40d`；
- 四策略均 100/100/0，所有 unavailable、invalid、duplicate、sample-limit 和 diagnostics 为 0；
- 计数守恒、pass 比例梯度、overall/phase intent、relation 和 reason 覆盖全部通过；
- midgame、near-open、critical 最低样本门槛全部通过；
- endgame 最低 700 门槛中，forced=583、25%=660、50%=663 失败，100%=777 通过；
- 273 项审计中只有上述三项失败；
- 单模块 11 项、相关 61 项、全量 407 项通过。

#### K-A2b2a：独立语料扩容恢复验收

状态：已完成，唯一判定 `strategy_router_coverage_verified`。

- 使用全新 seed `17000..17199`，四策略各 200 局；
- 保持 K-A2b2 的实现、策略、phase、分桶、采样、守恒和全部覆盖门槛不变；
- 完整运行两次并将报告、审计摘要与哈希保存在仓库外；
- canonical SHA-256 为 `ee321d18a50f923e92bbcc7e99c7e90a0ee87ac8b57b35b95e091f988c670c0e`；
- 四策略均 200/200/0，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 结构完整性 97/97、覆盖 176/176、总计 273/273 通过；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- 该结果只证明覆盖容量充足，不证明路由质量或胜率提升。

#### K-A3a：intent prompt payload 契约

状态：初版已实现，但严格复核未通过。唯一判定 `strategy_intent_prompt_contract_invalid`。

- formatter 只消费精确 `StrategyIntentContext`，不读取 observation、history、RAG、engine 或配置；
- available 且语义一致时输出完整 ready payload，其他输入整体 omitted；
- 固定 intent/reason/phase 文案映射，不透传任意文本；
- 严格字符预算，超限不截断、不输出部分内容；
- payload frozen/slots、JSON 友好、确定序列化且不修改输入；
- 本步未接入 DeepSeek prompt 或动作选择；
- 单模块 7 项、相关 43 项、全量 414 项通过。

当前缺失回归：

- higher-priority urgency 存在时，`weak_hand` / `stable_control` 必须 omitted；
- 双方都紧急时，`opponent_urgent` / `teammate_urgent` 不能绕过比较 reason；
- 队友控桌或紧急对手控桌时，后续 urgency/weak/control reason 不能被接受；
- `minimum_opponent_hand_count` 与 `urgent_opponent_ids` 必须一致；
- opponent table urgency 与 minimum/urgent IDs 必须不矛盾；
- hand strength 必须与 total score 阈值一致，control score 不得大于 total score。

#### K-A3a1：intent prompt 跨字段语义加固

状态：已完成，唯一判定 `strategy_intent_prompt_contract_hardening_verified`。

- 使用完整字段按 K-A1 优先级推导唯一 expected reason；
- reason/intent 与 expected reason 不一致时整体 omitted；
- 合法十种 reason 和三个公开 snapshot 保持逐字节不变；
- 不修改现有 agent/client/RAG/evaluation 或动作选择；
- 九类预注册反例全部 omitted；
- 单模块 11 项、相关 47 项、全量 418 项通过。

#### K-A3b：默认关闭的 intent prompt 消费接线

状态：已完成，唯一判定 `strategy_intent_prompt_wiring_verified`。

- 严格三态：off、shadow-only、prompt；prompt 必须依赖 shadow；
- 每次决策重置 intent 与 payload 审计字段；本地快捷路径跳过两者；
- 只有 ready payload 才增加类型化 client keyword；
- client 独立复核 payload，固定章节只插入一次；
- off/shadow-only/omitted/异常路径保持模型调用和动作等价；
- RAG、剪枝、fallback、config、CLI 和 evaluation 保持不变；
- client 拒绝手工篡改的类型、metadata、reason、边界行、行数和 char count；
- confidence 与 strategy intent 同时 ready 时顺序稳定且各出现一次；
- 定向 56 项、相关 88 项、全量 424 项通过。

#### K-A3c1：离线 prompt 覆盖与成本载体

状态：已完成，唯一判定 `strategy_intent_prompt_coverage_capacity_verified`。

- 四种 strategic-pass 策略使用独立对局和聚合状态；
- 按 midgame/endgame/near-open/critical 聚合 prompt pair；
- ready 必须精确插入一次，omitted 必须保持 off/on 相等；
- 记录 payload 与 prompt delta 字符和、最小值、最大值及 pair SHA-256；
- 报告不保留 prompt、observation、动作、玩家、手牌或逐样本内容；
- 不调用 DeepSeek、网络、真值或 `game._state`；
- seed `300..309` 双运行 canonical SHA-256 为 `032ff0964a0fe4c377c612f27263e553abfe22ad759d14b5714ebf788d280a20`；
- 四策略样本/ready 为 350/350、377/377、391/391、469/469；
- 16 个 phase bucket 全部 ready，零 omitted/invalid/mismatch/diagnostics；
- payload 74..90 字符，delta 83..99 字符；
- 定向 6 项、相关 52 项、全量 430 项通过。

#### K-A3c2：独立语料正式 prompt 覆盖验收

状态：已完成，唯一判定 `strategy_intent_prompt_coverage_benchmark_invalid`。

- HEAD / K-A3c1 检查点为 `1fca3270843d51c2b565b37e7823b57ed9b950b5`；
- seed `18000..18199`，四策略各 200 局，正式双运行耗时 65.371s / 65.002s；
- 两份 canonical JSON 完全一致，SHA-256 为 `35587b8d532dc9ba3fc8d82d6f6a690692362a31a908c066b2ad4783bfd1d148`；
- 16 个桶全部达到 ready 样本门槛，且 `sample = ready = exact insertion`；
- unavailable、invalid、omitted、duplicate、sample-limit、pair mismatch 与 diagnostics 全部为 0；
- 四个 near-open 桶均为 payload `84..91`、delta `93..100`，违反预注册上界 `89/98`；
- delta 仍严格等于 payload+9，失败来自预注册理论包络错误，不是插入或实现错误；
- 运行前后定向 6 项、相关 52 项、全量 430 项通过，`git diff --check` 通过；
- 原运行保持无效，不重跑、不补采、不事后追认。

#### K-A3c2a：字符包络契约封板

状态：已完成，唯一判定 `strategy_intent_prompt_envelope_contract_verified`。

- 只修改 `tests/test_strategy_intent_prompt.py`；
- 穷举四阶段×十种合法 reason，共 40 个真实 formatter 调用，全部 payload ready、diagnostics 为空；
- 全部满足 `char_count == len(text)`，逐组合字符数与预注册表精确一致；
- 理论 payload 包络固定为 midgame `74..81`、endgame `74..81`、near-open `84..91`、critical `83..90`；
- 对应 prompt delta 固定为 payload+9，即 `83..90`、`83..90`、`93..100`、`92..99`；
- 每阶段最大值均来自 `urgency_tie_block_opponent`；
- 定向 12 项、相关 60 项、全量 431 项通过，`git diff --check` 与禁止边界扫描通过；
- 未修改 formatter 文案、映射、runtime、benchmark 或任何业务代码；
- K-A3c2 原正式 invalid 结论不变，只授权使用全新 seed 的 K-A3c2b 恢复验收。

#### K-A3c2b：独立 seed 正式恢复验收

状态：已完成，唯一判定 `strategy_intent_prompt_coverage_recovery_verified`。

- HEAD / K-A3c2a 检查点为 `a8cf1291de2fde62c6c7ed7ecfeaa878671f5490`，运行前后工作区干净；
- 固定 seed `19000..19199`、rates `(0,25,50,100)`、级牌 `2`、`max_steps=5000`、每局每阶段最多 128 样本；
- 正式 benchmark 恰好运行两次，耗时 62.944s / 63.941s；报告和 canonical JSON 逐字节相同，SHA-256 为 `a3f6b35f791435af22ccf3e877e5b5d571028d9dc05d36ce506e10c2a31ad66b`；
- 每策略 200/200/0，四阶段 ready 最低样本全部达到；
- 16 个桶均满足 `sample = router available = payload ready = exact insertion`，其他状态与 diagnostics 全为 0；
- 字符范围落在 K-A3c2a 封板包络内，delta 的 sum/min/max 分别等于 payload 对应值加固定 9 字符开销；
- 定向 12 项、相关 60 项、全量 431 项通过；
- K-A3c2 原 invalid 不变，本结论只授权规划 evaluation-only 动作消融。

#### K-A3d1：策略意图成对动作消融载体

状态：已完成，唯一判定 `strategy_intent_action_ablation_harness_verified`。

- 仅新增 `evaluation/strategy_intent_action_ablation.py` 与 `tests/test_strategy_intent_action_ablation.py`；
- provider 必须由调用方注入，不创建 client、不读配置或环境、不联网；
- 四策略×四阶段分别以稳定 SHA-256 优先级选样，默认每桶 4 对，AB/BA 各 2；
- off/on 共用 observation、原始 legal actions、剪枝后的 prompt actions、phase 和 hand evaluation；on 只增加 `strategy_intent_prompt`；
- only-pass、一次出完、opening、router unavailable、payload omitted、少于两个 prompt 候选或 prompt pair 不精确时不调用 provider；
- provider 返回必须分类为 exception、malformed、no-action、非法类型、outside-legal、outside-prompt 或 valid；不使用 fallback；
- 两侧都必须尝试；both-valid 后聚合 same/changed、pass 和 pressure 选择，报告不得保留样本、prompt、动作 ID、玩家或手牌；
- deterministic fake provider 与 seed `400..409` 双运行报告完全相同，SHA-256 为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；
- 四策略×四阶段每桶 qualified≥4、selected=4、AB/BA=2/2、both-valid=4、changed=4；
- 每轮 128 次 provider 调用，off/on 各 64；所有错误分类与 diagnostics 为 0；
- 定向 8 项、相关 74 项、全量 439 项通过；不评价动作质量或胜率。

#### K-A3d2：同状态 RuleBased 分支续局质量代理

状态：已完成，唯一判定 `strategy_intent_action_quality_harness_verified`。

- 仅新增 `evaluation/strategy_intent_action_quality.py` 与 `tests/test_strategy_intent_action_quality.py`；
- 不修改 K-A3d1 模块、runtime、engine、client 或 prompt；
- 每个固定优先级入选样本保留内存 `deepcopy(game)`，只用公开 `observe()/legal_actions()` 验证 clone 等价，不读取 `_state`；
- provider off/on 均 valid 后执行分支续局；same action 复用一次 rollout，changed action 使用两个独立 clone；
- 后续所有玩家由独立 `RuleBasedAIAgent` 通过公开 API 推进，终局只读取 `step()` 结果和公开 `history.finish_order`；
- 比较顺序为队伍 win/draw/loss、队伍名次和、tie，不以 rollout 步数打破平局；
- 报告聚合 branch complete/fail、on/off/tie、changed 子集、W/D/L、名次和、步数和及 diagnostics；
- seed `500..509` 双运行报告完全相同，canonical SHA-256 为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；
- 四策略×四阶段每桶 selected=2、AB/BA=1/1、both-valid=2、changed=2、branch complete=4；
- 32 pair 全部 quality-evaluable，64 branches 全部完成，diagnostics 为空；
- 假 provider 的 on/off/tie=`5/11/16` 只验证载体，不代表真实模型质量或胜率；
- K-A3d1 兼容复验通过；定向 7 项、相关 80 项、全量 446 项通过。

#### K-A3d3a：真实模型质量试验前置审计

状态：历史两次执行均为 `precondition_failed`；当前新进程的环境 presence 与干净工作区已满足，等待重试同一步完成剩余前置。

- K-A3d2 已形成只含两个质量文件的检查点 `415c86dc5034ca85862f52e94d1406aa58042b98`；真实运行前工作区必须干净；
- 首次执行 HEAD 为 `a450fd2367b53ba455e904e1361422f9f965eb58`，工作区干净；7 / 80 / 446 项测试、`git diff --check`、K-A3d1/K-A3d2 固定 hash 与兼容检查均通过；
- 首次执行未显式取得 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY`，因此在配置门槛处停止；未读取 `.env`、未创建 runner、未联网或调用模型；
- 第二次执行仍缺少相同三项变量，按快速门槛停止且没有重复运行回归；
- 当前新进程已确认三项变量 present，工作区干净；锁定 endpoint/model 为 `https://api.deepseek.com` / `deepseek-v4-flash`；
- 重试顺序调整为先检查三项显式进程环境；仍缺失时立即报告 `precondition_failed`，不重复运行完整回归；
- `.env.example` 不计作显式进程环境，不得从中读取配置或写入真实密钥；其未提交改动会同时阻塞干净工作区前置；
- 本步不联网、不发送 probe、不创建 live runner，只复核测试、hash、非敏感 endpoint/model 与 key presence；
- 预注册 seed `600..609`、rates `(0,50,100)`、每 phase 2 对、共 24 pair/48 请求；
- timeout 60 秒、retries 0、持久后台最长 65 分钟；
- 后续 ledger/audit 必须证明 48 次请求全部使用 `deepseek-v4-flash`，无 `deepseek-v4-pro` 混用、替换或 fallback；
- 质量判定只比较同一 flash 模型的 off/on 分支，不与历史 pro 报告合并；
- 必须向用户展示明确 endpoint、model、请求数、timeout、重试和目的后请求授权；
- 未获授权时不得把配置存在视为默许，不得启动任何外部请求。

#### K-A3d3b：真实 strategy intent 动作质量小样本运行

状态：已执行但启动失败，唯一判定 `strategy_intent_live_quality_benchmark_invalid`。

- HEAD `f0a087a4146b0950764b8b08bf03ff6c15723d98`，K-A3d3a 的 7 / 80 / 446、固定 hash、兼容性和配置前置均通过；
- 唯一后台进程 PID `33612` 已退出；没有第二次运行、补采或恢复；
- 失败目录只保留 runner，SHA-256 为 `a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd`；
- process state、heartbeat、ledger、report、summary、completion 均不存在；request/ledger count=0；
- 因没有可审计 pair 或 rollout，不运行或解释任何质量守恒和描述性门槛。

#### K-A3d3c1：离线启动状态链加固

状态：已完成，唯一判定 `strategy_intent_live_startup_hardening_verified`。

- 首次尝试只读复核原 runner bytes/hash、PID 和启动边界，均与 K-A3d3b 失败报告一致；
- 因工作区不干净，在创建 recovery candidate 前停止；未运行 offline self-check、未创建第二进程、未联网或调用模型；
- 原 runner 首次 state 写入早于 `try/except`，且项目 imports 位于顶层；缺失证据只能标记 `startup_failure_before_state_write`；
- 父启动器必须在 spawn 前写 launch state，捕获 PID/exit code 和脱敏输出；
- 子 runner 必须在 project import 前写 bootstrap state，所有参数、目录、写入和 import 错误进入最外层保护；
- `--offline-self-check` 必须禁止 client/网络，request count=0，并覆盖正常、参数、目录、import 和写入失败；
- 正常 self-check 独立运行两次，易变字段外的结构化结果一致；
- 该结果只解锁使用全新 seed `700..709` 的 K-A3d3c2 前置；实际联网仍须重新取得明确授权。
- 父启动器与子 runner 的 SHA-256 分别为 `6a186d7c...e5ca84a`、`776f4504...b01e445`；最终审计 SHA-256 为 `aabebaeb...59af6e`；
- 两次正常 self-check 结构 hash 均为 `ede8bfc3...41e80ec`；缺失参数、无效目录、import 失败和原子写入失败均产生预期状态；
- request/network/client/suggest count 均为 0；未联网、未调用模型、未读取 `.env` 或 key 值。

#### K-A3d3c2：独立恢复 live 前置与授权

状态：已执行唯一 live run，判定 `strategy_intent_live_quality_recovery_invalid`。

- 只读复核 K-A3d3b invalid 与 K-A3d3c1 bootstrap 证据；
- 配置锁定 `https://api.deepseek.com` / `deepseek-v4-flash`，key 仅检查 presence；
- 使用全新 seed `700..709`，策略 0/50/100、每 phase 2 对、24 pair/48 请求；
- timeout 60 秒、retries 0、持久后台上限 65 分钟，formal live run 恰好一次；
- 授权前不得创建 live runner、启动进程或联网；必须重新取得明确授权，旧 K-A3d3b 授权无效；
- 授权后 runner 必须保留父 spawn 前和子 import 前状态、连续 ledger、脱敏失败证据与全部质量守恒。
- 实际完成 48/48 请求，off/on 各 24，全部 returned、零重试、零失败请求；
- report/audit summary 已写入，但 manifest/completion 缺失，child exit code=1；
- 子状态为 bootstrapping→imports_ready→startup_ready→running→completed→failed；
- 第 244–245 行错误地从 audit 目录读取 candidate-root runner metadata，导致 report_validation 阶段失败；
- 按完整性优先规则不解释 report 的质量、W/D/L 或策略结果；未重跑，授权已用尽。

#### K-A3d3c3a：独立只读恢复审计

状态：已完成，唯一判定 `no_observed_strategy_intent_action_quality_gain`。

- 原证据目录只读，前后文件集合、bytes、SHA-256 必须一致；
- verifier 独立重算 48 条 ledger、report、三策略四阶段、provider/pair/branch/W-D-L/quality 守恒；
- 验证 completed→failed 状态与第 244–245 行 manifest 路径错误，不信任原 summary verdict；
- 在新目录运行两次，canonical 输出逐字节一致，生成独立 recovery summary/manifest；
- 不补写原 manifest/completion，不联网、不调用模型、不读取 `.env` 或 key；
- 恢复完整性通过后才按 changed≥8、on/off better、team wins 顺序给出描述性判定。
- verifier 双运行逐字节一致，原 9 文件集合/hash 不变；48 request、24 pair 和全部质量守恒通过；
- changed=`7`，先于 on/off better=`2/1`、team wins=`8/6` 触发第一道门槛；
- K-A3d3c2 原 invalid 保持不变；strategy-intent prompt 默认关闭，不进入扩大验收。

#### 持续约束：软信号边界

- pass 只保留为公开行为事实，不作为默认软持牌证据或确定无牌；
- 所有 `likely` 结论带置信度和证据来源；
- 软信号不能覆盖 J-A 公开事实或 J-B 硬约束。

### 离线准确率

测试和评测环境可读取预设完整手牌作为 ground truth，但这些牌不能进入 AI runtime observation。

至少记录：

- 未见牌池准确率；
- 逐玩家 Top-K 点数召回率；
- 错误确认数；
- 外部剩余 20 / 12 / 8 张三个区间的推断准确率。

## 5. Step K：策略测试

- 固定 observation 的策略路由结果可复现；
- 队友少牌时可进入 `support_teammate`；
- 危险对手少牌时可进入 `block_opponent`；
- 弱牌优先 `run_out`；
- 强牌且无紧急威胁时可进入 `control`；
- RAG 只为已选策略提供证据；
- 近似明牌残局不能把低置信度猜测写成确定事实。

## 6. Step L：Botzone 本地 AI 接入测试计划

状态：L4-A3b1 已完成，定向 2、相关 18、全量 534 项通过，唯一判定 `botzone_live_smoke_recovery_authorization_ready`。用户已明确授权固定预算 L4-A3c；下一执行任务核对授权消息后运行一次前台无贡 smoke。L4-A2c5b2a 暂缓。

Phase 0 证据验收已完成：

- 官方裁判源码来源、31,136 bytes 与 SHA-256 已记录；
- claim 多重集、副本等价、顺序、非王替代和最多两张配子已定位到官方源码；
- 无贡 `deal×4 → player 0 play` 已定位到官方源码；
- 账号配置入口已脱敏确认；真实 URL/密钥不进入仓库，截图中暴露的值必须轮换。

最低测试集合：

- `tests/test_botzone_cards.py`：已完成；108 个牌 ID、花色/点数/王边界、两副副本 identity；
- `tests/test_botzone_protocol.py`：已完成 deal/play/pass、claim 重复、官方 `resist=false`、固定四槽 history、座位转换和 `TableView`；
- `tests/test_botzone_profile.py`：已完成；无贡 opening、tribute/return unsupported 与边界扫描；
- `tests/test_botzone_poll.py`：已完成；批量 request、finished/aborted、计数、UTF-8、CRLF 和注入防护；
- `tests/test_botzone_session.py`：事务、实体手牌、重连、多局、effect、history merge、本地座位和 schema v3 已完成；
- `tests/test_botzone_connector.py`：fake transport、match context、类型化 result、四座位 context 和官方首个 play 已完成；
- `tests/test_botzone_play_adapter.py`：已完成；座位映射、observation、table constraint、pass、自然动作和配子 action/claim；
- `tests/test_botzone_action_provenance.py`：已完成；输出只能来自原始 legal action 对应 `action_id`，矛盾 context 不创建 Agent；
- `tests/test_botzone_rule_agent_e2e.py`：RuleBasedAI 的 deal→play 关键回合、终局和无贡 profile 边界；
- `tests/test_botzone_adapter_observation.py`：已完成；轮次重放、精确 key set、wildcard table action、实体守恒与 context 一致性；
- `tests/test_botzone_http_transport.py`：已完成；GET/Header、timeout、重定向、响应上限、错误脱敏、response close、严格 ASCII Header 和 fake opener；
- `tests/test_botzone_runtime_config.py`：已完成；只读显式环境/参数、缺失配置、不导入 dotenv/根 config、仓库外绝对 state dir 与 preflight-only；
- `tests/test_botzone_runner.py`：已完成；退避/重置、finished/wall/cycle/failure/diagnostic 停止、退出码、fake gateway E2E 和零真实网络；
- `tests/test_botzone_live_preflight.py`：已完成；零网络启动审计、finished 敏感状态清理、最小 audit schema 和一局 fake smoke 守恒；
- `tests/test_botzone_rule_compatibility.py`：官方裁判/脱敏 Log 与当前 engine 的差分 fixture。
- `tests/test_botzone_bot_io.py`：已完成；外层 `requests/responses` 模型、可选官方字段、基数、inner-stage 解析、历史重放与 canonical response。
- envelope replay 与 response wrapper 场景已并入 bot_io、poll、connector、session、protocol 和 RuleBased E2E 相关测试，不另建含真实数据的 fixture。

验收边界：

- 协议与 unsupported stage 边界通过后可标记 `botzone_no_tribute_protocol_verified`；
- deal + play 端到端通过后可标记 `botzone_no_tribute_adapter_verified`；不得宣称完整支持 Botzone GuanDan；
- 真实联网测试必须另行取得用户明确授权；
- 真实测试桌必须显式设置“需要进贡=否”；收到 tribute/return 时该局验收失败，不生成替代动作；
- smoke 完成只证明接入可用，不证明胜率或策略提升；
- fixture 不得包含真实 URL、密钥、match ID、完整真实手牌或原始 Log。

L4-A2c1 离线诊断最低覆盖：

- PowerShell/`Start-Process` 参数能力；
- Python executable 前台基线与后台解析；
- 合成环境变量继承，只记录 present/missing；
- working directory 和参数引用；
- stdout/stderr 分离重定向；
- 短超时、PID/exit code 与脱敏异常；
- 修正启动方式连续两次离线成功；
- connector/GET/network count 严格为 0。

L4-A2c1 实际结果：六步矩阵通过，根因类别为 `stream_redirection`；`UseNewEnvironment` 不能消除失败，去除 PowerShell Redirect 后连续两次固定退出码 17。L4-A2c2 新增测试必须覆盖：

- launcher 内部 stdout/stderr 分流和文件关闭；
- 三个输出/audit 路径必须仓库外、绝对、互异且拒绝覆盖；
- 只允许固定 connector 参数，不允许 URL/state-dir/未知参数穿透；
- 合成环境继承、工作目录、参数和退出码；
- entrypoint 异常、非法路径、非法整数/bool 的稳定 fail-closed；
- Windows PowerShell 5.1 不带 Redirect 参数启动 launcher 的两次独立离线回归；
- network/GET/connector count 严格为 0。

L4-A2c2 实际结果：上述 launcher 测试全部通过，PowerShell 已不再承担流重定向；Python launcher 同进程分流并保持既有 connector 参数和退出码。L4-A2c3a 追加准入检查：

- L4-A2c2 检查点只含 launcher 与对应测试；
- 实际环境只查两项 Botzone 变量 presence，三项 probe 变量必须初始 missing；
- state dir 与专用 audit 目录前置为空；
- 既有 preflight-only 恰好一次并保持零网络；
- Start-Process 无 Redirect 参数的 offline probe 恰好一次，退出 17；
- probe 后无 connector/audit/state/进程残留，stdout/stderr 精确分流；
- 只有准入 ready 后才能请求新的固定预算 live 授权。

L4-A2c3a 实际结果：L4-A2c2 检查点范围和回归通过；环境 presence、probe 变量 missing、空 state、无残留进程与干净工作区均通过。preflight-only 超时后按序停止，未执行 launcher probe或任何 GET。L4-A2c4a 最低诊断覆盖：

- Python startup、runtime config import、main import graph；
- 合成显式配置加载；
- resolve/boundary/mkdir/tempfile/write/flush/fsync/replace/unlink 分阶段 heartbeat；
- `preflight_state_directory()`、main 函数与 module 子进程分别执行；
- 每阶段独立 10 秒上限和脱敏 faulthandler；
- 不使用真实 URL/state，不构造 transport/opener；
- request/GET/network/connector/live-launcher count 严格为 0。

L4-A2c4a 实际仅完成 startup；runtime import 的 `ModuleNotFoundError` 来自诊断脚本执行形状，不能作为项目结果。L4-A2c4b 必须新增以下载体门槛：

- 父进程 cwd 固定仓库根；临时 probe 仅经 `python -c + runpy.run_path` 执行；
- 不设置 PYTHONPATH；
- 两次 qualification 的 cwd/path/spec/origin 四布尔全部为 true 且一致；
- qualification 失败不执行正式阶段；
- 每个正式阶段执行前重复同一自检；
- 有效矩阵才允许形成 verified/inconclusive，harness 错误必须独立 invalid；
- 全程只用合成 URL/临时 state，网络与 connector 计数严格为 0。

L4-A2c4b 实际结果：qualification 与全部正式阶段通过，根因为 `not_reproduced`。L4-A2c5a 最低测试要求：

- 专用 module 在 runtime import 前先原子写 `bootstrapping`；
- 配置、state resolve/boundary/mkdir/tempfile/write/flush/fsync/replace/unlink、完成阶段均可审计；
- runtime callback 默认关闭时现有行为不变；
- 每类配置/file-op/callback/audit/interrupt/未知异常有稳定脱敏结果；
- audit 路径外部、绝对、新建且原子 JSON；
- 合成子进程 10 秒内完成、state 为空、阶段完整；
- 不导入主入口/runner/transport/connector/Agent，不读取 dotenv；
- request/GET/network/connector/live-launcher count 严格为 0。

L4-A2c5a 实际结果：专用 module、stage callback、稳定退出分类、原子 audit、异常清理与合成子进程均通过。L4-A2c5b 实际环境准入门槛：

- L4-A2c5a 检查点只含 `runtime_config.py`、`live_preflight.py` 和专属测试；
- 真实配置只由专用 module 内部消费，外部仅查 presence；
- state dir 前后为空，audit 目录前置为空；
- 专用 preflight 恰好一次、30 秒上限、不重试；
- 成功阶段精确完整，失败保留最后阶段；
- 不执行 live launcher、旧 preflight-only、connector 或 GET；
- ready 后仍需 L4-A2c5c，不直接申请 live。

L4-A2c5b 实际结果：检查点范围和 10/23/526 回归均通过；唯一真实环境运行在 30 秒后终止，audit 最后完成 `directory_ready`，没有 `temporary_opened`，state 仍为空，网络计数为 0，唯一判定 `botzone_instrumented_live_preflight_invalid`。L4-A2c5b1 诊断测试口径：

- 仓库外标准库载体先在全新临时目录完成一次资格验证；
- 真实 state 目录只执行一次，不重跑正式 preflight；
- 候选名生成、`os.open(O_CREAT|O_EXCL|O_RDWR)`、fdopen、write、flush、fsync、close、replace、unlink 均有调用前后 stage；
- 每个 probe 路径由本任务唯一拥有，禁止通配删除和扫描未知文件；
- 超时只报告最后未完成的原子操作和脱敏栈，不推断系统根因；
- state 前后为空，request/GET/network/connector/live-launcher 严格为 0。

L4-A2c5b1 实际结果：资格验证成功；真实目录单次探测 exit code 5，最后阶段 `exclusive_open_started`，清理 exit code 0，唯一判定 `botzone_state_tempfile_operation_boundary_verified`。L4-A2c5b2 诊断测试口径：

- 新载体先在第四个全新临时目录完成一次资格验证；
- 当前配置目录、同卷全新目录、本地应用数据全新目录按固定顺序各探测一次；
- 每次只执行一个 `os.open(O_CREAT|O_EXCL|O_RDWR)`，不重试、不补采；
- 异常只记录白名单类型、整数 errno/winerror、filename presence 和 candidate existence，不记录异常文本或路径；
- 每个目标使用独立任务前缀并只清理精确任务文件，所有目录事后为空；
- 结果只能划定目录/卷/进程范围，不得解释系统根因；
- request/GET/network/connector/live-launcher 严格为 0。

L4-A2c5b2 实际结果：qualification 成功；configured 与 same-volume 均返回 `PermissionError`、errno 13、winerror null并清空。local-appdata 因父载体将 evidence 子目录与 target 设为同名而未启动，summary/manifest 缺失，唯一判定 `botzone_exclusive_open_scope_diagnosis_invalid`。以下 L4-A2c5b2a 恢复口径保留但暂缓，不是当前下一步：

- 使用新 run ID、新 runner、全新 evidence root 和全新目标目录；
- 探针前验证所有 evidence/target resolve 路径两两不等、互不包含；
- 新目标前置不存在，configured state 前置存在且为空；
- 资格验证后，configured、same-volume、local-appdata 按固定顺序各执行一次；
- 旧 b2 的两项部分结果不得进入新 summary 或替代任何目标；
- 三目标完成后必须原子生成 summary.json 和 manifest.json；
- 异常脱敏、精确清理、空目录、进程与零网络守恒全部通过。

L4-A3a 最低测试口径：

- 顶层必需 `requests/responses`，满足 `len(requests)=len(responses)+1`；官方可选字段可缺省；未知字段和错误类型拒绝；
- 每条 inner request 继续使用现有 stage parser；`tribute/return` 仍 fail-closed；
- 首条 deal 与历史 response 可在无本地 session 时恢复本家实体手牌；pass 不扣牌，合法 action 精确扣一次；
- 历史 response/stage、level、座位、profile、实体牌或 claim 矛盾时不调用 Agent、不伪造动作；
- 无贡 play 的 `tribute_cards/return_cards` 必须是空 mapping，非空或 malformed 拒绝；
- deal、pass、自然动作和配子动作均输出 canonical `{"response":...}`；
- mock connector 验证 full-envelope digest、pending resend、ack 后 effect 提交和多 match 隔离；
- fixture 只用合成 ID，不保存真实 live 请求、完整真实手牌、URL、密钥、match ID 或 Header 值；
- 定向测试、全量 `python -m unittest discover -q`、`git diff --check` 与敏感内容扫描全部通过。

L4-A3a 实际结果：上述契约全部通过；Botzone 定向相关集合 47 项、全量 532 项通过，`git diff --check` 与敏感边界扫描通过。唯一判定 `botzone_bot_json_envelope_contract_verified`。该结果只覆盖离线合成输入，不能追认旧 smoke 或证明 live 可用。

L4-A3b 最低测试口径：

- 工作区差异严格限制为 L4-A3a 实现、对应测试和五份规划文档；
- 重跑 Botzone 定向集合、全量 532 基线和 `git diff --check`；
- 只暂存 allowlist，并以独立提交恢复干净工作区；
- 当前进程只检查 Botzone URL 为 present，不读取或输出值，不加载 `.env`；
- `%LOCALAPPDATA%` 下创建本任务独占的新空 state 目录；
- `python -m integrations.botzone --preflight-only` 恰好运行一次，30 秒内 exit 0 且固定输出 `preflight_ready`；
- preflight 前后目录为空，request/GET/network/connector count 全部为 0；
- 通过后只请求 L4-A3c 授权，不在同一步启动 connector。

L4-A3b 实际结果：L4-A3a 已提交为 `2ac51fb2...e11f1498`，提交后工作区干净；定向 50、全量 532 与 diff check 通过。唯一 preflight 在 30 秒内 exit 0、stderr 空、state 前后为空并删除，网络计数全为 0，但 `stdout_is_preflight_ready=false`。由于未保留合格 raw stdout，唯一判定 `botzone_envelope_live_smoke_preflight_invalid`，不得重试或追认。

L4-A3b1 最低测试口径：

- 新增 `tests/test_botzone_preflight_output.py`，只使用显式合成 HTTPS URL 和临时目录；
- direct `main(..., environ={})` 返回 0，文本精确为 `preflight_ready\n`，transport/opener 构造即失败；
- 两个独立 module 子进程从仓库根运行，环境移除全部 `BOTZONE_*`，stdout/stderr 用 binary PIPE；
- raw stdout 只允许 UTF-8 的 `preflight_ready\n` 或 Windows `preflight_ready\r\n`，normalized lines 精确一行；
- 拒绝 BOM、NUL、空格、额外行或文本，stderr 必须为空，state 必须为空；
- 两次 normalized 结果完全一致，request/GET/network/connector 为 0；
- 运行专属、相关、全量测试和 `git diff --check`；
- 通过只形成独立 `botzone_live_smoke_recovery_authorization_ready`，不改写 L4-A3b invalid。

L4-A3b1 实际结果：新增 `tests/test_botzone_preflight_output.py`；direct main 与两次 module binary PIPE 全部通过，transport/opener/request/GET/network/connector 为 0，state 临时目录为空。定向 2、相关 18、全量 534 和 diff check 通过；检查点 `28de0cb3...b1f331`。L4-A3b invalid 保持不变。

L4-A3c live smoke 验收口径：

- 必须先取得用户对当前 URL、RuleBasedAI、100 GET、120 秒 timeout、900 秒 wall、1 局和不重试的明确授权；
- 使用唯一前台进程，不使用 `Start-Process`、隐藏 launcher、runmatch 或第二 connector；
- 用户新建测试桌并明确选择“需要进贡=否”，不得复用旧桌；
- state/audit 位于全新 LocalAppData 路径，仓库保持干净；
- 成功必须为 exit 0、`finished_target`、finished=1、request/response/header 均大于 0、transport failure=0、diagnostics 空；
- 出现贡还、malformed、transport、limit、interrupt、audit 缺失或状态残留均判 invalid，不重跑；
- 报告只保留聚合计数，不读取或展示 URL、Header、match ID、手牌、history 或 session 正文；
- verified 只证明一局无贡接入可用，不形成胜率或策略提升结论。

L4-A3c 实际结果：唯一前台 connector 在首个请求后以 `malformed_request`、exit 5 停止；`requests_seen=1`，response/header/finished 均为 0，transport failure 为 0。用户未在进程结束前确认新建无贡桌，因此不能证明请求属于新桌。该结果永久为 `botzone_no_tribute_local_ai_smoke_invalid`，不得重试或补采。

L4-A3c1 最低测试口径：

- JSON 解码错误与 envelope 结构错误使用不同固定诊断；
- 当前 inner request、历史 response 与 replay/history 对齐错误分别归类；
- 所有对外诊断经过集中 allowlist，不使用异常正文或动态字段；
- 未知异常统一回退 `malformed_request`，不泄露 `str/repr`；
- 非法输入不调用 Agent、不准备 response、不发送 Header；
- connector 聚合准确的安全错误码并保持既有 `diagnostic_failure` 停止行为；
- 合法 deal/play/replay/pass/自然牌/配子路径逐字段不变；
- fixture 只使用人工合成最小结构，不复制真实 live 请求或完整手牌；
- audit 与输出不含 payload、match ID、牌 ID 列表、手牌、history、URL、Header、Cookie、密钥或异常正文；
- 运行定向测试、全量 `python -m unittest discover -q`、`git diff --check` 和边界扫描；
- 本步严格离线，request/GET/network/connector count 为 0。

L4-A3c1 实际结果：新增固定诊断契约后，新诊断 4 项、相关 Botzone 22 项、全量 538 项通过，`git diff --check` 与边界扫描通过。固定对外码为 `request_json_invalid`、`envelope_shape_invalid`、`inner_request_invalid`、`historical_response_invalid`、`replay_history_invalid`，未知异常为 `malformed_request`。唯一判定 `botzone_malformed_request_safe_diagnostics_verified`。

L4-A3c2 最低测试与准入口径：

- 工作区实现差异必须精确为 L4-A3c1 的五个代码/测试文件；
- 重跑新诊断、相关 Botzone、全量 538 基线和 `git diff --check`；
- 只提交五个实现/测试文件，提交后工作区干净；
- 当前进程只检查 URL 配置为 present，不读取值或 `.env`；
- 使用全新仓库外 state 目录，恰好运行一次 `--preflight-only`，30 秒内 exit 0；
- stdout 规范化后精确为 `preflight_ready`，stderr 为空，state 前后为空并精确清理；
- request/GET/network/connector count 为 0，不启动 launcher 或 connector；
- ready 后只请求新的 live 授权，且用户必须同时确认旧本地 AI 测试桌已结束；
- preflight 失败不得重试、联网或申请授权。

最新 live 实际结果：唯一运行 exit 0、`finished_target`、finished 1，但 request/response/header 均为 0。该结果永久判为 `botzone_no_tribute_local_ai_smoke_invalid`；它暴露了 finished 停止条件的来源缺口，不是 smoke 成功。

L4-A3d1 最低测试口径：

- `finished_seen` 保留网关原始计数，新增 qualified 完成计数；
- runner 只按 qualified 完成停止，不能按 raw finished 停止；
- qualified 必须按同 match 关联当前 connector 实例处理的合法 play response、成功 Header 发送/ack 与四人 finished；
- 未知、历史、重复、aborted、非四人、只有 deal、play pending 未发送、transport 失败和 cleanup 失败均不合格；
- 多 match 不得拼接全局 request/response/header 计数形成假成功；
- 合格 match 最多计数一次；stale 与合格 finished 同批时 raw/qualified 分别守恒；
- `exit_code_for()` 不允许 qualified 未达标时返回成功；
- audit schema 同时保存 raw/qualified 聚合，不含 match ID 或请求内容；
- 既有 pending/ack、重启恢复、tombstone、诊断优先级和合法 E2E 回归通过；
- 全量测试、`git diff --check` 和敏感边界扫描通过；
- 本步 request/GET/network/connector live count 为 0。

## 6. 对局评测

单元测试不能代替策略评测。每次策略改动应使用固定种子进行 A/B 对局，并轮换座位，至少记录：

- 胜 / 负 / 平；
- 平均完赛名次；
- 非法动作数；
- API 调用数和失败数；
- 开局高价值牌消耗；
- 近似明牌阶段的猜牌准确率。

在没有 A/B 数据前，只能声明“功能已接入”，不能声明“策略已提升”。

## 7. 测试失败说明

如果测试无法运行，最终说明必须包含：

- 实际运行的命令；
- 失败测试名；
- 是实现失败、环境问题还是外部 API 问题；
- 未验证的剩余风险。

## 8. Botzone 直接上传 Bot 测试

### 8.1 当前 Python 3.6.5 规则基线

对应文件：

- `botzone_upload_py36/__main__.py`
- `tests/test_botzone_upload_py36.py`
- `dist/guandan_rule_ai_py36.zip`

长期保持：

- 使用 Python 3.6 grammar，可由标准库运行；
- ZIP 根目录精确包含入口 `__main__.py`，不超过上传大小限制；
- deal 输出 canonical `{"response":[]}`；
- play 输出 `[action, claim]`，动作实体来自当前手牌；
- 历史 response 只扣除一次已出实体牌；
- free lead、跟单、无可压动作 pass 均有回归；
- stderr 为空，正常路径只输出一行 JSON；
- 不读取 `.env`、connector URL 或本机配置。

用户已报告该基线在 Botzone 完整运行两局。此结果是人工 smoke，不替代自动测试，也不覆盖逢人配完整合法动作。

### 8.2 U0 DeepSeek 探测包最低测试

下一步新增测试必须覆盖：

- 与规则基线相同输入下，`response` 逐字段完全相同；
- 凭据缺失/非法时零网络调用并返回规则动作；
- fake opener 覆盖成功、超时、DNS/connect、TLS、HTTP 4xx/5xx、非法 JSON和未知异常；
- 诊断只使用固定脱敏分类，不包含 key、URL、Header、响应正文或异常正文；
- 每局最多探测一次，后续回合通过非敏感 `data` 标志跳过；
- HTTPS endpoint、`deepseek-v4-flash`、非流式、短超时、零重试的请求形状；
- DeepSeek 正文永不进入 Botzone response/debug/data；
- 测试使用合成 key 和 fake opener，真实 DNS/socket/HTTP 调用数为 0；
- 新 ZIP 与 `guandan_rule_ai_py36.zip` 并存，不能覆盖稳定规则基线。

U0-A1 实际结果：

- `botzone_deepseek_probe_py36/__main__.py`、对应测试和独立 ZIP 已完成；
- 定向规则基线 + 探测包 12 项通过；
- 全量 556 项通过；
- 探测 ZIP 4,982 bytes，SHA-256 `82ba5fd18b333b7a389316478042d53b07a22e0d4e4c00f992ade010fedf239c`；
- 稳定规则 ZIP hash 保持 `29e7ec827abf0ff6673bfeafab254cb9cc2174edc37bf1c802dcc15a346de351`；
- 唯一判定 `botzone_deepseek_probe_package_verified`。

U0-A2 人工准入结果：

- 固定状态：`probe_dns_or_connect_failed`；
- Botzone verdict OK，无决策超时；
- 规则动作合法，对局完整结束；
- 首个探测输出约 61 ms；
- 用户存储凭据契约通过，但没有 HTTP 或模型响应；
- 唯一判定 `botzone_deepseek_egress_admission_blocked`。

该人工结果只记录固定状态与聚合运行信息；附件中的牌、request、response 和账号相关内容不得复制到 fixture 或仓库。禁止用重复探测、代理、IP 直连、关闭 TLS 或延长重试来改写该结论。

### 8.3 后续完整体 parity 测试

进入 U1 后，应使用同一公开局面比较 Python 3.11 engine 与 Python 3.6 上传实现：

- 自然牌与逢人配完整合法动作集合；
- Botzone 108 实体 ID、carrier/claim 和重复虚拟 claim；
- 同型压制、炸弹层级、同花顺和王炸；
- pass、接风、done/pass_on 与历史窗口；
- action ID/provenance 只能映射回候选集合。

进入 U3 后，应增加模型输出分类、短超时、零重试、非法候选回退和 RuleBased 动作可用性测试。进入 U4 长时运行后，还必须覆盖当前 request-only 输入、内存状态、进程重启后的完整 envelope 恢复和 keep-running marker/flush 契约。

## 9. Botzone connector DeepSeek 恢复测试

### 9.1 L5-A1 离线接线

必须新增并通过：

- 默认 rule 模式不加载 AppConfig、DeepSeekClient、RAG 或 DeepSeekAIAgent；
- 显式 deepseek 模式使用 fake client 选择合法 action ID，并由既有 provenance 生成 Botzone response；
- deal、pending 重发、ack 重放和本地快捷动作不会产生重复模型调用；
- 模型异常、超时、malformed suggestion、`None`、严格 bool、字符串、负数、越界和 outside-legal ID 均回退合法 RuleBased 动作；
- fallback 结果必须再次通过 `require_legal_action_id()` 和 provenance 回查；
- pass、自然牌和单配子 response 编码保持不变；
- 同一 match/player 复用 Agent，不同 match/player 隔离，finished 后清理；
- transport failure、重启、pending resend、ack 不重复调用模型或扣牌；
- 缺失 key 时 deepseek 模式在 transport 前失败，rule 模式保持可用；
- Agent 输入不包含 match key、request digest、Botzone 实体 ID、Header 或原始 envelope；
- 测试只使用 fake client/transport，真实 DNS/socket/HTTP/Botzone/DeepSeek 请求数为 0。

最低回归：

```text
python -m unittest tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_runner -q
python -m unittest discover -q
git diff --check
```

通过 L5-A1 只能判定离线接线成立，不代表真实 Botzone connector、DeepSeek 可达、动作质量或胜率已经验证。真实 smoke 必须作为 L5-A2 单独获得授权。

L5-A1 实际结果：实现检查点 `71d9119`，定向 23 项、全量 565 项和 `git diff --check` 通过，判定 `botzone_deepseek_connector_offline_wiring_verified`。

### 9.2 L5-A1a 启动与诊断加固

进入 live 前必须补充：

- 默认 handler 精确区分 `agent_failure`、`invalid_agent_action_id` 和 `missing_provenance`；
- DeepSeek fallback 精确区分主 Agent 失败、`rule_fallback_failure`、`invalid_rule_fallback_action_id` 和 `missing_provenance`；
- 参数化证明主 Agent/fallback 每次最多各调用一次；
- deepseek 缺 key 或本地组合失败时，Botzone transport 和 runner 构造次数均为 0；
- `--preflight-only --agent deepseek` 使用合成配置完成本地组合，输出固定 `preflight_ready`，不调用模型、DNS、socket、HTTP 或 Botzone poll；
- 默认 rule preflight 与既有 LF/CRLF stdout 契约保持不变；
- cache、pending/ack、finished cleanup、response provenance 和 RuleBased E2E 回归保持通过。

L5-A1a 实际结果：实现检查点 `aac59d5`，定向 23 项、全量 569 项和 `git diff --check` 通过，判定 `botzone_deepseek_connector_hardening_verified`。

### 9.3 L5-A2a 真实环境零网络 preflight

必须验证：

- HEAD/工作区/回归满足门槛；
- Botzone URL 与 DeepSeek key 只检查 present，endpoint/model 只检查是否匹配锁定值；
- 使用全新仓库外 `%LOCALAPPDATA%` state 目录，不复用历史 state；
- `--agent deepseek --preflight-only` 恰好执行一次，30 秒硬上限且不重试；
- exit 0、stdout 单行 `preflight_ready`、stderr 空、state 最终为空、无残留进程；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 和 `suggest_action_id()` 均为 0；
- summary 不含 URL、key、Header、路径敏感片段、牌、request/response、prompt、reasoning 或异常正文。

通过只能判定 `botzone_deepseek_connector_live_preflight_ready`。真实 connector 与模型调用必须放在 L5-A2b，并重新获得明确授权。

L5-A2a 前置实际结果：检查点、工作区、23/569 回归和四项脱敏环境元数据通过，但 `%LOCALAPPDATA%` 仓库外目录不可写；preflight 子进程未启动，全部网络计数为 0，判定 `precondition_failed`。

### 9.4 L5-A2a1 临时目录恢复

- 不修改代码，不重复 23/569 回归；
- state 根必须来自系统标准临时目录，候选必须全新、随机、仓库外且初始为空；
- 不复用 `BOTZONE_STATE_DIR`、历史 state 或固定路径，不申请提权；
- 目录资格通过后，原 preflight 命令恰好执行一次，30 秒硬上限且不重试；
- 成功门槛仍为 exit 0、单行 `preflight_ready`、空 stderr、空 state、无残留进程与全部网络/模型请求计数为 0；
- 目录创建失败时保持 `precondition_failed`，不得改试其他目录；
- 子进程启动后的任何门槛失败判 `botzone_deepseek_connector_live_preflight_invalid`。

实际结果：临时目录资格通过；唯一 preflight exit 0、单行 `preflight_ready`、stderr/state/残留进程为空、约 190 ms，全部网络与模型请求计数为 0。判定 `botzone_deepseek_connector_live_preflight_ready`。

### 9.5 L5-A2b 单局 live smoke

授权与执行门槛：

- 当前 Botzone URL、`https://api.deepseek.com`、`deepseek-v4-flash`；
- 单个前台 connector、单个新无贡桌；
- 最多 100 cycles、poll timeout 120 秒、DeepSeek timeout 60 秒、retries 0、wall 3600 秒；
- 全新系统临时 state/audit；完成 1 个 qualified match 即停；
- 用户必须在 connector 显示已连接后再创建测试桌；
- 任何历史授权不可复用，失败后不重跑。

成功必须有 exit 0、`finished_target`、qualified finished、非零 request/response/header、零 transport failure、空 diagnostics、Botzone 无非法动作/超时、state/audit 无敏感内容且无残留进程。

当前 runtime 未独立统计模型调用、成功和 fallback。即使 smoke 通过，也只能判 `botzone_deepseek_connector_no_tribute_smoke_verified`，不能证明 DeepSeek 实际有效返回；该可观测性属于 L5-A3。

首次授权实际结果：endpoint/model/预算已授权，但没有明确授权发送本家未公开手牌及决策上下文；执行在进程创建前被安全审查拒绝。connector/network count 为 0，临时 state 已删除，audit 未创建，判定 `precondition_failed: sensitive_outbound_authorization_missing`。

### 9.6 L5-A2b1 敏感出站授权

恢复前必须在授权中明确：

- 发送本家当前手牌牌面与张数；
- 发送公开历史、桌面状态、玩家公开剩余张数/完赛信息；
- 发送 engine 合法候选动作、手牌评估、记牌摘要、场景标签和 RAG 片段；
- 目标为 `https://api.deepseek.com` / `deepseek-v4-flash`；
- 理解这些数据包含本家未公开手牌并离开本机；
- 不发送 Botzone URL/key、match/session、实体牌 ID、其他玩家隐藏牌或 `.env` 内容；
- 100 GET、60 秒、零重试、单进程、3600 秒、一局预算不变。

只有完整授权后才能创建新 state/audit 并启动唯一进程。

实际结果：完整授权后，23 项定向回归和全部快速门槛通过。唯一 connector 成功显示已连接，但在用户确认新桌开始前 exit 5。audit 聚合为 cycles=1、requests=1、responses=0、headers=0、finished=0、transport failure=0、`envelope_shape_invalid=1`；state 为空且无残留。请求未进入 Agent 或 DeepSeek。判定 `botzone_deepseek_connector_no_tribute_smoke_invalid`，不得重跑。

### 9.7 L5-A2b2 外层信封安全子分类

离线测试必须覆盖八类 envelope shape 门槛：顶层类型/key、缺失必需字段、未知字段、非法可选字段、requests 容器、responses 容器、空 requests、请求/响应基数。

要求：

- 公开父诊断继续为 `envelope_shape_invalid`；
- detail 是固定低基数枚举且每个反例唯一；
- 合法 envelope 不产生 detail；
- inner/history/replay 诊断不被误分类；
- connector/runner/audit 只聚合 detail，不保留输入、牌、match、长度或异常正文；
- 既有 Botzone 和 DeepSeek runtime 回归保持通过；
- 所有测试使用合成数据，网络计数为 0。

实际结果：实现检查点 `37bdd0d`。八种固定 detail、父诊断兼容、非 shape 诊断隔离、connector/runner allowlist 聚合和 audit v3 均已覆盖。定向 24 项、全量 572 项、`git diff --check` 与边界扫描通过；唯一判定 `botzone_envelope_shape_subdiagnostics_verified`。

### 9.8 L5-A2b3 v3 恢复准入

- 复核运行 24 项定向测试和 diff check；
- 唯一真实进程是 `--agent deepseek --preflight-only`，30 秒、全新系统临时 state、零网络；
- 必须 exit 0、单行 `preflight_ready`、空 stderr/state、无残留；
- 项目所有者必须确认全部旧本地 AI 测试桌已关闭；
- 本阶段只准备并请求 L5-A2b4 授权，不执行 live。

实际前置结果：endpoint/model 匹配，但 DeepSeek timeout/retries 与锁定的 60/0 不一致。未创建 connector/state 子进程，Botzone/DeepSeek/network request 为 0，授权未消耗，判定 `precondition_failed: deepseek_budget_mismatch`。

### 9.9 L5-A2b3a 预算配置恢复

- 新 Codex 进程中 timeout 必须是非 bool 数值 60，retries 必须是非 bool 整数 0；
- 只输出 present/match 布尔值，不输出配置正文；
- 重新运行 24 项定向和 diff check；
- 使用全新系统临时 state 运行唯一一次零网络 deepseek preflight；
- preflight 通过后只请求旧桌清理确认和后续授权，不启动 live。

实际结果：重启后 timeout/retries 仍未被当前执行宿主继承；其余门槛和 24 项定向通过。state/preflight/connector 未创建，网络计数为 0，授权未消耗，判定 `precondition_failed: deepseek_budget_mismatch_after_restart`。

### 9.10 L5-A2b3b 子进程预算锁定

- 同一 PowerShell 子环境显式设置 timeout=60、retries=0；
- AppConfig 探测只输出 `deepseek_budget_ready` 或 `deepseek_budget_invalid`；
- 探测不构造 client/Agent/transport，网络计数为 0；
- 探测通过后，同一子环境运行唯一 preflight；
- preflight 的 exit/stdout/stderr/state/残留/零网络门槛保持不变；
- 不修改持久环境或 `.env`，不启动 live。

实际结果：当前进程六项门槛、检查点、24 项定向、diff check 与残留检查通过。唯一 preflight 约 171 ms、exit 0、stdout=`preflight_ready`、stderr/state 空、临时目录删除且无残留；随后补充的显式 60/0 AppConfig 探测返回 `deepseek_budget_ready`，未重跑 preflight。网络与模型请求为 0，判定 `botzone_deepseek_connector_v3_preflight_ready`。

### 9.11 L5-A2b3c 人工桌面门槛

- 项目所有者确认所有历史本地 AI 测试桌已结束或关闭；
- 下一次只在 connector 已连接后创建一个新无贡桌；
- 不同时保留或创建第二个活动桌；
- 本阶段不运行测试、preflight 或 live，只在确认后提出 L5-A2b4 授权问题。

实际结果：项目所有者完成旧桌清理确认并授权 L5-A2b4。唯一 connector 连接成功后，在新桌开始确认前 exit 5；audit v3 聚合为 requests=1、responses/headers/finished=0、transport failure=0、`envelope_shape_invalid=1`、`envelope_required_fields_missing=1`。state 为空、无残留、未进入 Agent/DeepSeek。判定 `botzone_deepseek_connector_no_tribute_smoke_invalid`，不得重跑。

### 9.12 L5-A2b5 必需字段缺失画像

- 六种固定 profile 覆盖缺 requests、缺 responses、空 object、inner-stage candidate、optional-only、其他 object；
- 父诊断/detail 保持兼容；
- 其他 detail、inner/history/replay 和合法 envelope 不产生 profile；
- connector/runner 双层 allowlist，未知 profile 不进入 audit；
- audit 只聚合 profile，不包含 key/value、长度、hash、match、牌或异常正文；
- 全部使用合成输入，网络与模型请求为 0。
### L5-A4e9 / L5-A4f1 执行验收

L5-A4e9 未取得 direct connector 的持续 session ID，state/audit/网页对局均为空，判定 invalid。该结果不是新增代码测试。

随后完成两项离线执行资格：合成 20 秒 Python 进程由统一执行工具返回 session ID 并可继续轮询至 exit 0；合成 URL 的 D 盘仓库外 `--preflight-only --agent rule` 在系统扩展权限下返回 `preflight_ready`，目录最终为空。两项均未调用 Botzone 或 DeepSeek。

L5-A4f1 不新增代码回归。执行验收要求 direct connector 命令自身使用系统扩展权限和统一 TTY session；初次 yield 必须返回 session ID 且没有 exit code。之后才允许 Browser 连接/建桌。最终仍复核 exit/finished/request、transport/protocol、v8/v4/token、DeepSeek observability 与无残留守恒；失败不得重试或新建诊断载体。
### L5-A4f1 手动闭环与 L5-A4f2 单对验收

项目所有者手动前台 DeepSeek 局的只读 evidence 已通过：v8 audit 804 bytes / `ee747bc2...236d1`，request=response=Header=27、qualified finished=1、transport failure=0；一次 long-poll timeout 不触发失败。Agent decision 26=local shortcut 9+model 17，model attempt/result=17/17 success、fallback=0；v4 最小 tombstone 与 audit token 一致。该结果不是代码测试，也不证明策略优于 RuleBased。

L5-A4f2 不新增代码测试。执行验收覆盖同 seed/seat/opponents/profile 的 rule/deepseek 两局、独立 v8/v4/token、正常结果、transport/timeout 分类、策略观测守恒以及现有 benchmark 对单对输入的严格聚合。任一局失败即停止，不重试、不继续、不恢复 16 局批次。
### L5-A4f2 结果与 L5-A4f3 自动化验收

L5-A4f2 game 1 的 v8/v4、22 组请求、21 次 rule primary、正常结果和零异常均通过，但网页 seed 与预注册 `31001` 不同，因此 pair invalid；这不是代码测试失败。

L5-A4f3 不新增代码回归。执行验收新增 Browser DOM readback：提交前必须精确验证 game、tribute、seed、seat、level、first/last 和三个非敏感 opponent-selected 布尔值；同时要求 direct connector 持续 session、v8/v4/token、RuleBased 来源、请求/finished 和 transport/protocol 守恒。任一字段或运行门槛失败不得提交/重试。
### L5-A4f3 evidence 与 L5-A4f4 UI 顺序验收

L5-A4f3 的 `32001` v8/v4 evidence 本身有效：33/33/33 请求、qualified finished 1、RuleBased、零 transport failure、token 匹配；但 audit 在目标桌提交前产生，因此运行归属失败，不能计入 pilot。该结论不是代码测试失败。

L5-A4f4 不新增代码测试。执行验收要求两次 Browser DOM readback：connector 前与页面已连接后分别核对 GuanDan、无贡、seed、seat、level、first/last、目标 Bot match 和三个对手槽；completion audit 必须在最终开始游戏后产生。其余 v8/v4/token、RuleBased 来源、request/finished 与 transport/timeout 守恒保持不变。
### L5-A4f4 结果与 L5-A4f5 浏览器写保护

L5-A4f4 audit 为 exit 130、request/Agent=0、4 次 timeout、空 state；页面出现房主关闭，但缺少可归因动作证据，因此只判 UI 生命周期失败，不归因误点。

L5-A4f5 不新增代码测试。执行验收新增点击白名单、每次点击前后 DOM 证据、两次完整 readback，以及最终开始游戏后的 browser write action count=0。对局页只允许 snapshot/URL/title/screenshot 和 connector polling；其余 v8/v4/token、RuleBased、request/finished 和 timeout 守恒保持不变。
### L5-A4f5 结果与 L5-A4f6 UI 契约验收

L5-A4f5 在 connector/目录/网络均为 0 的状态下停于游戏选择确认后的主页，说明 browser 白名单本身不足以证明 UI 状态转换；这不是代码回归失败。

L5-A4f6 不新增代码测试。执行验收覆盖 visible modal scope、GuanDan selected/checked proof、modal 内唯一 confirm、确认后的 modal disappearance/form readiness，以及“载入上次配置/开始游戏”同表单存在。最终提交、connector、GET、DeepSeek 和 runmatch 均必须为 0。
### L5-A4f6 UI 契约与 L5-A4f7 执行验收

L5-A4f6 已验证 visible game selector、GuanDan current option、唯一创建按钮、验证码门槛及后续表单 readiness；`载入上次配置`/`开始游戏！` 各唯一，所有 connector/network/table-submit count 为 0。

L5-A4f7 不新增代码测试。执行验收要求复用已保留表单、两次完整 readback、connector 提交前存活、唯一开始点击及提交后 Browser write count=0；同时保持 v8/v4/token、RuleBased 来源、request/finished 和 transport/timeout 守恒。标签页或验证码状态变化不得自动重走。
### L5-A4f7 基线与 L5-A4f8 单对验收

L5-A4f7 的执行验收全部通过：两次 readback、提交后 browser write=0、34/34/34、qualified=1、33 rule primary、零模型/fallback/transport failure，以及 v8/v4/token/无残留守恒。该结果不是新增代码测试。

L5-A4f8 不新增代码回归。执行验收覆盖两局条件相等、独立 readback/session/v8/v4/token、rule 与 deepseek 来源守恒、正常结果和 existing benchmark 单对聚合。任一局失败立即停止；单对结果不得解释为统计或胜率结论。

### L5-A4g1 计划测试：benchmark idle timeout 与显式范围

- 锁定零 timeout/空 diagnostics 与非零 timeout/唯一匹配 diagnostic 两条有效路径。
- 锁定 timeout 缺诊断、计数不等、零 timeout 带诊断、混合诊断及真实 transport failure 的无效路径。
- 新增 selected-seat schedule 的严格类型、非空、去重、范围、顺序和 AB/BA 一致性测试。
- 锁定正式 `build_paired_schedule()` 仍覆盖每 seed 的四个座位。
- 单 seed/单 seat 聚合只要求声明的一对，不产生未声明座位的 incomplete。
- 报告 dataclass、`to_dict()`、canonical JSON 与隐私字段集合保持不变；测试只用合成 audit，不读取 `36001` live evidence。

### L5-A4g1 验证结果与 L5-A4g2 恢复门槛

- 检查点 `569d5431...`：定向 13 项、全量 624 项、`git diff --check` 通过。
- selected-seat 的严格输入、顺序、正式赛程对应关系和单 seat 完整性已覆盖。
- timeout 的匹配 diagnostic 有效路径与缺失、错数、混合、真实 failure 等反例已覆盖。
- L5-A4g2 不新增代码测试；先复跑 13/624 回归，再对封存 evidence 执行两次字节一致的只读聚合。
- 恢复验收要求 requested/valid=`1/1`、invalid/incomplete/duplicate=`0/0/0`、空 diagnostics、token 归属和源哈希前后不变。

### L5-A4g2 结果与 L5-A4h1 执行验收

- L5-A4g2 双运行字节一致，源 inventory 不变；聚合 requested/valid=`1/1`，其余失败计数为 0。
- L5-A4h1 开始前复跑 benchmark 13 项、全量 624 项和 `git diff --check`。
- 离线准入覆盖 16 个 state 目录原子写资格、manifest 守恒、rule/deepseek 各一次零网络 preflight。
- 逐局验收覆盖双 readback、持续 connector、单次开始点击、v8/v4/token、request/finished、timeout/diagnostic和策略来源守恒。
- 最终正式 schedule 必须聚合为 requested/valid=`8/8`、四 seat 各 `2/2`、AB/BA=`4/4`、空 diagnostics。

### L5-A4h1 失败边界与 L5-A4h2 原子写入门槛

- L5-A4h1 未运行测试后的 live 阶段；失败只发生在 manifest 原子落盘证据不足。
- L5-A4h2 writer 自检必须逐项证明 `exclusive_create/write/flush/fsync/close/replace/readback/canonical/temp_absent`。
- 正式 manifest 回读 bytes 必须与预计算 canonical payload 完全一致，临时文件必须不存在，bytes/SHA-256 固定后不可改写。
- 原子门槛通过后沿用 13/624 回归、16 个 state 资格、双模式 preflight、逐局 v8/v4/token 和最终 8 对聚合验收。

### L5-A4h2 结果与 L5-A4h3 UI 门槛

- L5-A4h2 已证明 manifest 九阶段自检、16 个 state 探针和双模式 preflight 可通过；失败不是代码或网络测试失败。
- L5-A4h3 的 UI 验收新增三类：其他玩家桌可忽略、当前账号旧桌暂停清理、归属未知时请求项目所有者确认。
- 大厅列表非空不得直接产生 invalid；确认等待不计为 connector timeout 或批次失败。
- 不得通过点击、加入或关闭既有桌来判断归属；只有本批次新桌允许写操作。
- 其余 13/624 回归、原子 writer、16 局 evidence 和最终 8 对聚合门槛不变。

### L5-A4h3 结果与 L5-A4h4 progress 演练

- L5-A4h3 第 1 局的 live evidence 验收通过；失败属于 progress schema，不是 connector 或策略测试失败。
- L5-A4h4 在正式 progress 前演练 ready、game 1..16 完成转换和九种 failure_stage invalid 转换。
- 缺/多字段、bool、越界、完成计数跳号、hash 不匹配和非法 null/status 组合必须拒绝且不覆盖合法 progress。
- 每次演练及正式更新都验证 atomic writer 九阶段、canonical 回读和临时文件清理。
- progress 门槛通过后沿用 13/624、双模式 preflight、16 局 v8/v4/token 与最终 8 对聚合验收。

### L5-A4h4 结果与 L5-A4h5 编排资格

- L5-A4h4 没有实际运行测试；失败属于命令解析，不是回归失败。
- L5-A4h5 的每条基线命令必须独立调用；临时 qualification script 先 py_compile，再验证仓库 module origin。
- qualification-only 两次运行使用合成输入，必须逐字段一致、临时目录清空、全部网络与 Agent 计数为 0。
- 解析/quoting/import-path 资格错误允许修正并重跑；实际代码测试或文件操作失败才形成 precondition failure。
- 正式 manifest 落盘后继续原 13/624、progress 全状态演练、双 preflight、16 局 evidence 与 8 对聚合验收。
