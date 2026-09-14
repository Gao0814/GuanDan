# 给 Coding Codex 的下一任务 Prompt

为`short_endgame_plan`补充prompt-first的专用公开策略输入，但不修改或退役后置动作覆盖。既有固定fixture中，本家自由出牌且手持`6S,7S,JH,JD`，最少分组首手ID为`{1,2,5}`；当前通用`control / stable_control`提示下，一次零重试真实DeepSeek请求在守卫前选择了严格更差的单J动作，判定`short_endgame_prompt_raw_model_not_ready`。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务没有适用的Botzone live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及`agents/short_endgame_planner.py`、`agents/deepseek_ai.py`、`agents/strategy_router.py`、`agents/strategy_intent_prompt.py`、`integrations/botzone/agent_runtime.py`和对应测试。
3. 检查Git工作树，确认HEAD包含规划检查点、`7499ccc`及其验收上下文。若存在外部修改，保持不动且不得混入提交。

## 【目标】

- 在`agents/short_endgame_planner.py`抽取一个独立于模型选择的共享公开机会函数，建议命名`minimum_group_free_lead_action_ids()`：只在完整、合法结构的公开observation与canonical legal actions证明本家1–4张自由出牌、所有动作可由本家实体手牌组成、每条剩余路径可完整分组，并且至少存在一个严格更差首手时，返回按原始动作顺序排列的最少分组action IDs；证据不足、所有首手并列或范围外返回`None`。
- 让现有`strictly_better_free_lead_action_ids()`复用该共享分析/结果，同时保持对每个selected action ID的当前返回值和fail-closed行为完全不变。不得复制两套分组算法。
- `StrategyIntentContext`新增固定布尔公开字段表示该机会是否成立，并进入`to_dict()`、unavailable默认值和prompt严格校验。router只调用共享机会函数，不自行实现第二套牌组搜索。
- router新增专用reason `short_endgame_minimum_groups`，intent=`run_out`。优先级保持`can_finish_now`第一、`teammate_big_joker_preservation`及既有跟牌语义不变；该free-lead机会应先于通用紧迫度、`weak_hand`和`stable_control`分支，使所有现有短残局守卫适用局面都能收到专用提示。
- prompt为该reason提供明确但不执行动作的公开策略说明：本家仅1–4张且当前自由出牌，完整canonical动作证明不同首手会导致不同的最少剩余分组数；优先选择使全部手牌所需分组数最少的首手，避免无谓拆散已有组合。不得枚举、过滤或替模型选择action ID，不得声称后续一定获得牌权。
- Botzone factory继续通过现有strategy-intent接线自然获得新prompt；不增加新开关或Botzone专用分支。

## 【保持不变】

- `DeepSeekAIAgent`中的`_plan_short_free_lead()`调用、后置改写、冻结selector、`short_endgame_plan` source、模型outcome计数和adapter处理必须保持行为不变。本任务不退役、扩大或缩小守卫。
- 不修改RAG场景/语料、engine、公开action契约、fallback、Botzone协议、audit schema/version、legacy source分类或conditional模式。
- 不恢复`teammate_control_block`、`danger_opponent_block`或任何RuleBased成功模型后置覆盖。
- 不访问网络、真实DeepSeek、Botzone、Edge、`.env`或`D:\VsCodeProject\BotzoneWorkspace`，不新增依赖。

## 【测试要求】

至少覆盖：

- 共享机会函数在固定4张fixture精确返回`(1,2,5)`；现有selected 1/2/5继续返回`None`，selected 3/4继续返回`(1,2,5)`。
- 全部首手分组数并列、hand count超出1–4、跟牌、pass/动作字段畸形、动作ID重复、手牌/载体不守恒、路径无法完整分组等场景继续fail closed，且router不产生专用reason。
- 固定fixture的router从`control / stable_control`变为`run_out / short_endgame_minimum_groups`，新增布尔字段为true；prompt为`ready / run_out`且包含“最少剩余分组”和避免拆组语义。
- 篡改布尔字段、reason、free-lead/hand-count关系或其他上下文字段时prompt继续fail closed；机会为false时既有reason优先级和序列化结果不漂移。
- fake模型在固定fixture返回单J时仍由现有守卫改为原始最优ID并记录`short_endgame_plan`；返回1/2/5时仍保持原始ID与`model` source。
- Botzone factory捕获到新专用prompt；RAG scene/phase/action_context仍为`endgame / near_open_endgame / endgame`，不因本任务变化。

至少运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.\.venv\Scripts\python.exe -m unittest tests.test_short_endgame_planner tests.test_deepseek_step_e tests.test_strategy_router tests.test_strategy_router_benchmark tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_botzone_deepseek_agent_runtime -q
.\.venv\Scripts\python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
.\.venv\Scripts\python.exe -m unittest discover -q
git diff --check
```

## 【完成标准与提交】

完成标准：短残局最少分组机会由一个共享、公开、fail-closed真值提供；固定fixture得到`ready / run_out / short_endgame_minimum_groups`专用提示；后置`short_endgame_plan`与所有既有边界保持原行为；全量测试通过。完成后不在本任务调用真实模型，下一轮再用同一fixture做一次守卫前复放。

只暂存并提交本任务产生的最小业务代码和测试修改，不提交规划docs、AGENTS或外部变化。最终报告列出共享函数契约、router优先级、prompt语义、守卫未变证据、修改文件、测试命令与结果、commit hash、最终Git状态及当前范围内剩余风险。
