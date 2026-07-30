---
id: exp_general_boundary_001
corpus: experience
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [legal_actions, control]
priority: medium
keywords_cn: [经验, 合法动作, 策略参考, 不能裁决]
---

# 经验库使用边界

经验只影响候选合法动作内部的排序倾向，不能替代规则，也不能生成动作。最终仍只能从候选 action_id 中选择；当经验与规则口径冲突时，必须以 legal_actions 和 engine/ 为准。

---
id: exp_lead_opening_strong_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [strong]
action_context: [free_lead]
topic: [opening, control, bomb]
priority: high
keywords_cn: [强牌, 开局, 首出, 控局, 保留炸弹]
---

# 强牌早期首出：保留控制力

强牌开局倾向先处理弱路或小路，保留炸弹、王、级牌、同花顺等控制资源。除非候选动作可以直接出完，或没有合理的普通动作，否则避免过早暴露高控制力牌型。最终仍只能从候选 action_id 中选择。

---
id: exp_lead_opening_medium_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [medium]
action_context: [free_lead]
topic: [opening, pair, run_out]
priority: high
keywords_cn: [中牌, 开局, 首出, 对子, 试探, 减少手数]
---

# 中牌早期首出：试探与减手

中牌信息不明时，倾向优先考虑对子试探，或选择自然三带二、顺子、连对等能减少总手数的候选动作。避免为了短期主动权过早交出高价值控制资源。最终仍只能从候选 action_id 中选择。

---
id: exp_lead_opening_weak_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [weak]
action_context: [free_lead]
topic: [opening, weak_escape, singles, run_out]
priority: high
keywords_cn: [弱牌, 开局, 首出, 孤张, 脱手]
---

# 弱牌早期首出：减少拖累

弱牌开局不应盲目争头游，倾向优先减少孤张和总手数。若有对子、自然三带二、顺子、连对等更能减手的候选动作，可优先考虑；若只能出单张，倾向选择较高单张而不是明显小单张。最终仍只能从候选 action_id 中选择。

---
id: exp_follow_response_basic_001
corpus: experience
scene: [follow_response]
phase: [midgame, opening, any]
hand_strength: [any]
action_context: [follow]
topic: [follow_response, opponent_pressure, pass]
priority: high
keywords_cn: [跟牌, 压制, pass, 收益, 代价]
---

# 跟牌压制：先看收益

跟牌时不要只看能否压住，还要考虑压住后的收益和代价。若压制会明显拆坏结构或交出过高资源，而局面收益有限，可以考虑保留资源；若能抢回关键节奏、阻断对手或帮助队友，则压制价值提高。最终仍只能从候选 action_id 中选择。

---
id: exp_follow_bomb_timing_001
corpus: experience
scene: [follow_response]
phase: [midgame, endgame, any]
hand_strength: [any]
action_context: [follow]
topic: [bomb, straight_flush, joker_bomb, opponent_pressure]
priority: high
keywords_cn: [炸弹, 同花顺, 天王炸, 压制, 阻断]
---

# 跟牌压制：炸弹使用时机

炸弹、同花顺、天王炸通常是高价值资源。倾向在抢回出牌权、阻断对手快走、保护队友关键节奏或接近终局时使用；避免仅因“能压”就机械提前消耗。最终仍只能从候选 action_id 中选择。

---
id: exp_wildcard_timing_001
corpus: experience
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [wildcard, run_out, control]
priority: high
keywords_cn: [逢人配, 通配, 自然动作, 消耗, 结构]
---

# 逢人配使用时机

逢人配灵活度高，倾向用于明显改善结构、减少手数或形成关键压制的候选动作。若自然动作与逢人配动作收益接近，通常优先保留逢人配；若逢人配能直接带来明显收益，则可积极考虑。最终仍只能从候选 action_id 中选择。

---
id: exp_teammate_support_001
corpus: experience
scene: [lead, follow_response, endgame, any]
phase: [midgame, endgame, any]
hand_strength: [any]
action_context: [free_lead, follow, endgame, any]
topic: [teammate_support, control, run_out]
priority: medium
keywords_cn: [队友, 快走, 配合, 放行, 节奏]
---

# 队友快走时配合

当队友剩余手牌较少时，倾向优先考虑帮助队友尽快走完，避免无意义抢掉队友可能接管的节奏。需要压制还是放行，只能在候选合法动作中选择，不能基于猜测构造动作。

---
id: exp_opponent_pressure_001
corpus: experience
scene: [follow_response, endgame, any]
phase: [midgame, endgame, any]
hand_strength: [any]
action_context: [follow, endgame, any]
topic: [opponent_pressure, bomb, control]
priority: high
keywords_cn: [对手, 快走, 阻断, 压制, 抢回主动]
---

# 对手快走时压制

当对手剩余手牌较少或即将出完时，阻断价值上升。可提高压制、抢回主动权以及必要时使用高价值资源的权重，但仍不能突破 legal_actions 的候选边界。

---
id: exp_endgame_run_out_001
corpus: experience
scene: [endgame]
phase: [endgame]
hand_strength: [any]
action_context: [endgame]
topic: [endgame, run_out, opponent_pressure]
priority: high
keywords_cn: [残局, 跑牌, 出完, 少牌, 终局]
---

# 残局跑牌

残局倾向优先考虑能直接减少手数、争取出完或阻断对手出完的候选动作。控制资源价值会随局面变化而上升或下降，关键是候选动作是否能实际改变终局节奏。最终仍只能从候选 action_id 中选择。

---
id: exp_strong_control_001
corpus: experience
scene: [lead, follow_response, any]
phase: [midgame, any]
hand_strength: [strong]
action_context: [free_lead, follow, any]
topic: [control, bomb, joker_bomb]
priority: medium
keywords_cn: [强牌, 控局, 王, 炸弹, 控制力]
---

# 强牌控局

强牌不一定要每手都强压，倾向保留能改变节奏的控制资源，在收益更高的节点使用。普通候选动作能维持节奏时，可优先保留王、炸弹、同花顺等关键资源。最终仍只能从候选 action_id 中选择。

---
id: exp_weak_escape_001
corpus: experience
scene: [lead, lead_opening, follow_response, any]
phase: [opening, midgame, any]
hand_strength: [weak]
action_context: [free_lead, follow, any]
topic: [weak_escape, run_out, singles]
priority: medium
keywords_cn: [弱牌, 脱手, 孤张, 减少手数]
---

# 弱牌脱手

弱牌倾向把目标放在减少拖累和保留可走路径上。能减少孤张、缩短未来出牌轮次的候选动作通常更有价值；但在跟牌时仍要评估压制代价，不能为了短期出牌拆坏全部结构。最终仍只能从候选 action_id 中选择。
