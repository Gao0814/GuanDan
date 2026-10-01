---
id: exp_general_boundary_001
corpus: experience
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [legal_actions, control]
priority: high
keywords_cn: [经验, 合法动作, 策略参考]
strategy_domain: [overall_priority]
guidance_mode: source_principle
---

# 总体目标与冲突优先级

适用条件：任何合法候选比较。策略目标：先处理立即走完及公开紧急性，再改善本家结构。建议倾向：在减少手数、保留控制和协同之间按公开局面排序。反例与调整：经验不裁决合法性，具体牌权或组合损失可推翻一般倾向。

---
id: exp_lead_opening_strong_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [strong]
action_context: [free_lead]
topic: [opening, control, singles]
priority: high
keywords_cn: [强牌, 开局, 首出, 小单, 控制]
strategy_domain: [opening_free_lead, control_return_resource]
guidance_mode: source_principle
---

# 强牌开局的小单首攻

适用条件：强牌自由首出，且完整动作集能证明有不拆自然组合的小单与独立可用的回手资源。策略目标：用较低成本的单张试探，同时保留后续争取牌权的路线。建议倾向：比较自然小单与中间单张，不按固定点数或花色套公式；保留可实际单出或成组回手的王、级牌、A等资源。反例与调整：队友/对手公开紧急、单张属于顺子或对子、资源本身要拆组、控制路线不清或存在明显牌型冲突时让模型比较，不本地直出。

---
id: exp_lead_opening_medium_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [medium]
action_context: [free_lead]
topic: [opening, pair, triple]
priority: medium
keywords_cn: [中性, 开局, 首出, 对子, 三张]
strategy_domain: [opening_free_lead, uncertainty_probe]
guidance_mode: source_principle
candidate_requirements: [natural_group_single]
---

# 中性开局表达

适用条件：中性牌力的自由首出，且canonical动作中存在自然对子/三张和结构安全单张。策略目标：在表达牌型、清理孤张和保留回手间比较。建议倾向：将对子/三张作为可核验路线，而不是“先出对子”的公式。反例与调整：较低成本单张、已成组合受损、队友控桌或危险对手接近走完都可推翻该倾向。

---
id: exp_lead_opening_shape_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [any]
action_context: [free_lead]
topic: [opening, pair, triple, straight, hand_structure, control]
priority: high
keywords_cn: [开局, 首出, 对子, 三张, 顺子, 余组, 回手]
strategy_domain: [opening_free_lead, hand_structure, control_return_resource]
guidance_mode: source_principle
candidate_requirements: [opening_natural_shape]
---

# 开局成型牌型与余组比较

适用条件：开局自由首出，完整canonical候选中存在不使用逢人配、且不拆已识别同点组的自然对子、三张或顺子。策略目标：结合公开牌力与余牌结构选择首出表达，同时保留可核验的控制或回手路线。建议倾向：比较小单、成型组牌或顺子出后剩余点数组、孤张、拆组与资源成本；只有公开结构形成清晰且唯一的结构优势时才适合简化为本地定式，候选取舍不清则交由模型。反例与调整：顺子可能拆对子/三张，成型组牌可能损害更好的回手、队友协同或控制资源；未识别到用途不证明留牌未来无用，立即出完和公开紧急性也可改变判断。

---
id: exp_lead_opening_weak_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [any]
action_context: [free_lead]
topic: [opening, run_out, singles]
priority: high
keywords_cn: [弱牌, 开局, 总手数, 孤张, 组牌]
strategy_domain: [hand_structure, opening_free_lead]
guidance_mode: source_principle
---

# 结构组牌与拆牌成本

适用条件：自由领牌且完整canonical候选可由本家公开手牌组成。策略目标：降低动作后所需手数并保留有边际价值的自然组合。建议倾向：逐个比较动作后的点数组、孤张和被拆开的对子/三张/连续结构；少打一张留下的牌是否值得保留，要与余组/孤张负担、结构损失和控制资源成本一起核对。若没有可证的组合用途且留牌增加负担、另一合法路线不损更高价值结构，可条件性倾向减少手数。反例与调整：未识别到用途不证明未来无用；立即出完、危险对手阻断、队友协同或有把握的回手计划可以改变局部取舍。

---
id: exp_midgame_control_001
corpus: experience
scene: [lead, follow_response]
phase: [midgame]
hand_strength: [any]
action_context: [free_lead, follow]
topic: [control, follow_response, joker]
priority: high
keywords_cn: [王, 级牌, A, 回手, 控制]
strategy_domain: [control_return_resource, follow_control]
guidance_mode: source_principle
---

# 控制牌与牌权争夺

适用条件：中局领牌/跟牌且完整候选中确有控制资源动作。策略目标：让资源消耗与可见牌权收益相称。建议倾向：比较自然普通路线、控制单张与炸弹/通配等候选，并只把后续控桌当作可能性，不当作保证。反例与调整：对手公开接近走完时可提高阻断优先级；队友控桌且不紧急时可让牌，避免为了“留资源”或“抢控制”机械选择。

---
id: exp_midgame_teammate_001
corpus: experience
scene: [lead, follow_response]
phase: [midgame, endgame]
hand_strength: [any]
action_context: [free_lead, follow]
topic: [teammate, support, control]
priority: high
keywords_cn: [队友, 协同, 让牌, 牌型]
strategy_domain: [teammate_coordination]
guidance_mode: source_principle
---

# 队友协同与让牌

适用条件：队友控桌且可让可接。策略目标：本队走牌/名次，争权/续领/回手送牌。建议倾向：难走完不轻易顺接，留牌送搭档。据此推导：弱压制接牌需收益抵成本；已有压力可先让看对手投入。不能立即出完、无公开紧急且拆完整炸无足够收益时倾向让，减张/盖队友≠协同。反例与调整：出完、紧急阻断、可核对控制/重组收益可推翻；争权投入后被反压也有成本，不保证反压、不猜暗牌。

---
id: exp_midgame_block_001
corpus: experience
scene: [follow_response, lead]
phase: [midgame, endgame]
hand_strength: [any]
action_context: [follow, free_lead]
topic: [opponent_pressure, control, block]
priority: high
keywords_cn: [对手, 阻断, 紧急, 剩余张数]
strategy_domain: [danger_opponent_block, follow_control]
guidance_mode: source_principle
---

# 危险对手阻断

适用条件：对手公开余张很少或危险对手正在控桌，并且canonical动作确有合法压制/阻断路线。策略目标：限制其公开走牌窗口，同时控制资源成本。建议倾向：把pass、普通压制和资源型压制与本家/队友走牌一并比较。反例与调整：不从断张推出暗牌；本家走完、队友更紧急或压制无法形成合理后续路线时可以放弃阻断。

---
id: exp_bomb_wildcard_001
corpus: experience
scene: [lead, follow_response, endgame]
phase: [midgame, endgame]
hand_strength: [any]
action_context: [free_lead, follow, endgame]
topic: [bomb, wildcard, control]
priority: medium
keywords_cn: [炸弹, 逢人配, 通配, 控制]
strategy_domain: [bomb_wildcard_management]
guidance_mode: soft_hypothesis
candidate_requirements: [bomb_or_wildcard]
---

# 炸弹与通配牌管理

适用条件：完整canonical候选确实含炸弹或逢人配；同点不同长度的自然炸弹只有在两侧都属于当前合法候选且公开出后结构可核验时才作自然残牌比较。策略目标：评估少出所留下实体牌的边际用途，并与炸弹强度/牌权机会、余组负担和多出牌资源成本共同权衡。建议倾向：有可识别自然组合、可能的回手/控制资源或公开协同用途时，说明其保留理由及代价；若只留下无已识别配合的散张或增加余组，而另一候选不损更有价值结构/控制资源，可条件性倾向一并打出。对子、三张、炸弹和连续结构只是可能重叠的线索，不自动等于高价值；未识别到用途不证明未来无用。通配路线不混作自然残牌结论。反例与调整：这是可撤回软假设，不是“必须炸”或固定长度顺序；用途不明时只比较已证成本，不断言未来合法走牌或牌权，一次出完、公开紧急、队友/对手牌权和更高价值结构均可改变取舍。

---
id: exp_endgame_run_out_001
corpus: experience
scene: [endgame]
phase: [endgame]
hand_strength: [any]
action_context: [endgame]
topic: [endgame, run_out, control]
priority: high
keywords_cn: [残局, 剩余张数, 回手牌, 出完, 调整]
strategy_domain: [endgame_planning]
guidance_mode: source_principle
---

# 残局规划

适用条件：公开余张进入残局阶段或有严格可证明的最少分组首手。策略目标：协调一次出完、可回手资源、队友/对手公开紧迫性和后续分组。建议倾向：将余组数仅视为结构估计，并比较自然收尾与控制路线。反例与调整：估计不保证牌权或完整走牌；炸弹资源、公开阻断和队友送牌可推翻静态分组口诀。

---
id: exp_card_memory_001
corpus: experience
scene: [any]
phase: [opening, midgame, endgame]
hand_strength: [any]
action_context: [any]
topic: [control, card_memory, uncertainty]
priority: medium
keywords_cn: [记牌, 王, 级牌, A, 10, 5, 断张]
strategy_domain: [uncertainty_probe, control_return_resource]
guidance_mode: source_principle
---

# 不确定信息与试探成本

适用条件：公开历史可核验且需要规划试探/控制。策略目标：用公开已出牌和明确剩余信息减少不确定性。建议倾向：仅记录本规则双副牌内实际公开出现的牌与尚未见到的类别；将断张、未见牌和对手未跟牌视为不确定信号。反例与调整：未见牌不等于某人持有，公开不跟不证明缺牌；不得据此断言炸弹、控制牌或搭档偏好。

---
id: exp_soft_pair_probe_001
corpus: experience
scene: [lead_opening, lead, follow_response]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead, follow]
topic: [pair, probe, bomb, structure]
priority: low
keywords_cn: [对子, 侦察, 控制, 三带二, 顺子, 炸弹]
strategy_domain: [uncertainty_probe, hand_structure, bomb_wildcard_management]
guidance_mode: soft_hypothesis
candidate_requirements: [natural_pair]
---

# 可撤回的对子试探假设

适用条件：公开动作中确有自然对子；若存在同点自然单张，则按完整关系对照比较。策略目标：评估清理两张、传递牌型和观察/控制成本。建议倾向：对子可作为待核验路线，小对子也可能有后续组合价值；不把“对子先行”设成统一顺序。反例与调整：此为可撤回软假设；低成本安全单张、紧急阻断、队友控桌、保留回手或更小结构损失均可推翻。

---
id: exp_soft_single_cost_probe_001
corpus: experience
scene: [lead_opening, lead]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead]
topic: [opening, singles, probe, uncertainty]
priority: low
keywords_cn: [中间单张, 低成本, 试探, 自由领牌]
strategy_domain: [opening_free_lead, uncertainty_probe, control_return_resource]
guidance_mode: soft_hypothesis
candidate_requirements: [natural_single_cost]
---

# 自然单张成本与试探路线

适用条件：至少两种自然单张均在完整canonical动作中存在，且当前首出不会拆散已成的同点对子/三张等组合。策略目标：比较较低成本清理与保留较高单张作为后续试探/牌权路线。建议倾向：低单张和较高单张都可能合理，不套用固定点数或花色顺序，也不据此猜测对手暗牌；仍须核对各动作对顺子等整体余组的影响。反例与调整：可用回手资源、队友协同、危险对手、整体组牌变化或更高价值牌型均可推翻；这只是可撤回假设。

---
id: exp_soft_straight_flush_bomb_cost_001
corpus: experience
scene: [lead_opening, lead]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead]
topic: [bomb, straight_flush, structure, control]
priority: low
keywords_cn: [同花顺, 炸弹, 拆组, 资源, 余组]
strategy_domain: [bomb_wildcard_management, hand_structure]
guidance_mode: soft_hypothesis
candidate_requirements: [straight_flush_bomb_fragment]
---

# 同花顺与炸弹组拆分假设

适用条件：完整canonical自由领牌中，同花顺路线会拆动至少两个自然四张点数组，且也有对应自然四炸候选。策略目标：比较一次压制价值、拆组损失与炸弹资源消耗。反例与调整：这是可撤回假设，不要求保留炸弹；一次出完、公开阻断或当前牌权需求可以推翻。

---
id: exp_soft_steel_plate_strength_001
corpus: experience
scene: [lead_opening, lead]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead]
topic: [steel_plate, control, structure]
priority: low
keywords_cn: [钢板, 大小, 强度, 保留, 余组]
strategy_domain: [hand_structure, control_return_resource]
guidance_mode: soft_hypothesis
candidate_requirements: [steel_plate_strength]
---

# 自然钢板强弱与保留假设

适用条件：自由领牌时至少两种不同主点数的自然钢板均为完整canonical候选。策略目标：比较先清理较小钢板与保留较大钢板作为后续控制路线。反例与调整：不推断对手持有小钢板；整手分组、队友/对手紧急性、立即出完和回手价值均可推翻，不能固定为“留大不留小”。

---
id: exp_soft_triple_pair_gradient_001
corpus: experience
scene: [lead_opening, lead]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead]
topic: [triple_with_pair, pair, structure]
priority: low
keywords_cn: [三带二, 携带对子, 梯度, 余组]
strategy_domain: [hand_structure, uncertainty_probe]
guidance_mode: soft_hypothesis
candidate_requirements: [triple_pair_kicker_gradient]
---

# 三带二携带对子梯度假设

适用条件：同一自然三张主组有至少三种完整canonical自然对子携带路线。策略目标：比较带走中间对子后保留大小对子路线与当前余组。反例与调整：不规定固定大小顺序；自然组合、立即出完、队友/对手紧急性和实际回手价值可推翻此可撤回假设。

---
id: exp_soft_triple_repartition_001
corpus: experience
scene: [lead_opening, lead]
phase: [opening, midgame]
hand_strength: [any]
action_context: [free_lead]
topic: [triple, triple_with_pair, singles, structure]
priority: low
keywords_cn: [拆三张, 单张, 三带二, 重组, 余组]
strategy_domain: [hand_structure, opening_free_lead]
guidance_mode: soft_hypothesis
candidate_requirements: [triple_split_repartition]
---

# 拆三张后的三带二重组假设

适用条件：公开手牌有至少三组自然三张与自然对子，且canonical动作同时包含拆三张的单张和另一组的自然三带二。策略目标：比较先出单张后保留两组对子/三张重组空间与立即出三带二。反例与调整：结构兼容不保证后续牌权；立即出完、公开紧急性和整体手数可推翻此可撤回假设。
