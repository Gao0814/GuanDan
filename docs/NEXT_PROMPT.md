# Coding任务：接通已有简短reason的显式调试入口

工作目录D:\VsCodeProject\GuanDan，继续cao。先核对AGENTS、CLEAN_HANDOFF、当前Git及相关代码；按Skill名称/description匹配后才读对应全文。普通客户端/接口修改不自动加载Botzone托管、游戏审计或清理Skill；若需要核对原局证据，使用botzone-game-audit的相关流程，不重做全部旧审计。

## 目标与已确认缺口

所有者询问是否应让DeepSeek解释所选动作以便调试。当前system已经要求JSON `{action_id, reason}`，真实原请求重放5次均报告有reason和reasoning_content，因此不是缺少解释指令。本轮先让已有短解释可被显式调试读取，并同时区分模型自述与可复现资源事实；不先调权重或修策略，不要求模型额外长推理。

已核对源码：

- agents/deepseek_client.py解析action_id，但丢弃JSON reason；DeepSeekSuggestion仅含action_id和SSE reasoning。
- integrations/botzone/agent_runtime.py的Strict客户端在有/无deadline两条成功路径重新包装结果并剥离自由文本；默认factory verbose=False。
- agent成功返回合法原ID，失败才走已有回退。当前游戏decision trace和落盘schema禁止模型自由文本。

原请求重放任务已经完成，不能再次执行旧5请求计划。按执行报告，同body拆K场景得到K/A/A；队友控桌场景重放选三带二仍损失一组自然炸弹。Planning独立确认原输入、展示闭环、返回ID对应的实体变化及脚本发送机制；没有留存原响应，实际HTTP结果与解释仍是执行报告证据。“模型把不出炸当保炸”尚为假设，不据概念摘要定根因或幻觉。

## 实现边界

1. 用最小兼容方式提取JSON中的短reason，与reasoning_content分开命名和处理。缺失、非字符串、空白或过长reason不得使合法action_id失效、触发重试/回退或改变选择；长文本有固定预算，旧构造/调用方式保持兼容，不把完整模型响应复制到诊断结构。
2. 提供显式启用的调试读取机制，使通过默认factory/Strict路径的成功选择也可在内存取得当次短reason和对应原始ID。具体可用已有回调或小型诊断结果，不指定必须增加CLI开关/长期缓存。默认关闭，不把自由文本写进stage trace、decision trace、聚合audit、日志或固定workspace现有文件；不启用会打印URL/完整模型内容的verbose。先保持现行落盘边界，勿把“输出解释便于调试”扩大为保存完整模型自由文本。
3. 调试读取方可将短reason作为当次自述查看；并按公开手牌与真实carrier复用现有结构/资源计算，提供实际动作是否拆掉完整自然炸弹、是否直接用炸弹、是否消耗控制单张等必要事实。不能将“普通牌型”直接标成“保住炸弹”，不根据reason关键词自动判事实、策略优劣或覆盖选择。已有资源事实能复用就不新增同义统计器/第二套规则。
4. 诊断与本次有效选择绑定：每次新决策清理旧数据；超时、无效ID、回退、本地快捷、跨局和晚到的旧worker不得带出前一手/其他局的解释。默认Strict仍剥离长reasoning；解释读取失败不能影响合法动作、既有source/outcome、Header或ACK事务，不为获取解释再请求模型。
5. 范围限于client、agent/Strict调试接线及直接受影响的必要tests。不改engine规则、模型请求body、候选展示、M9/M10、RAG或生产选牌偏好；不存原请求副本，不创建通用审计框架、阶段工具或新常驻副本。实现前自行定位统一接线点，若更小的接口足够可偏离上述实现建议并说明。

## 验证与交付

本轮真实API请求0，不启停connector/操作网页或修改旧证据。只运行本次相关的测试方法：用假SSE/现有factory检查短reason存在、缺失/畸形、长reasoning隔离、默认关闭、有/无deadline成功及失败/下一次决策、晚到结果/回调异常等会改变结论的路径；已有覆盖足够就复用，不机械跑整份文件或全量。

原证据D:\VsCodeProject\BotzoneWorkspace\games\2026_10_1_15-08-15_000046可只读用于必要机制核对：决策5中ID5拆四K为三K，ID2不损完整四K；决策15中ID25为普通三带二、自然四张10→两张。不要将私有手牌/body写进永久测试或共享报告；用相似合法载荷验证机制，不以固定K/10/ID作产品分支。

验收关注：合法成功原ID完全不变；短reason能经真实factory组合的显式调试入口读取；无解释仍能正常出牌；默认与落盘无自由文本；跨次/跨局/失败/晚到结果不误绑定；模型自述和实际结构事实明确分开。解释能读取仅是调试接线收益，不声称策略改善或胜率收益。

提交前做反补丁自检和完整diff检查，仅按明确路径提交本轮自有业务/tests，勿提交Planning docs。最终简报说明统一实现、触及文件、实际验证命令/结果、如何显式启用和读取短解释（禁网例即可）、commit、最终Git状态及真实范围内剩余风险，交回Planning复审。
