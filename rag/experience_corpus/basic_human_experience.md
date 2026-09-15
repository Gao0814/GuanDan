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

适用条件：强牌、自由首出且自然小单不拆组合。策略目标：以低成本表达主动性并保留回手资源。建议倾向：先考虑较小自然单张，保留王、级牌、A和可控组合。反例与调整：队友/对手紧急、组合受损或无回手资源时交由局面比较推翻。

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
---

# 中性开局表达

适用条件：自由首出且存在对子或三张候选。策略目标：在表达计划、观察牌势和保留后续路线之间权衡。建议倾向：把对子/三张视为可供模型核验的中性表达。反例与调整：不把它当固定首手；公开紧急性或结构代价可推翻。

---
id: exp_lead_opening_weak_001
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [weak]
action_context: [free_lead]
topic: [opening, run_out, singles]
priority: high
keywords_cn: [弱牌, 开局, 总手数, 孤张, 组牌]
strategy_domain: [hand_structure, opening_free_lead]
guidance_mode: source_principle
---

# 结构组牌与拆牌成本

适用条件：开局或自由领牌。策略目标：减少总手数、改善牌型并减少孤张。建议倾向：比较动作后的点数组和孤张，避免无谓拆散对子、三张或连续结构。反例与调整：局势变化、牌权计划或紧急阻断可覆盖单纯结构目标。

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

适用条件：中局跟牌或领牌。策略目标：保留可重新取得牌权的资源并避免无意义争夺。建议倾向：比较王、级牌、A和炸弹等明确控制资源的消耗。反例与调整：对手临近走完或队友已控桌时，普通控制保留可让位。

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

适用条件：公开可见队友剩余张数或当前控桌。策略目标：帮助更可能走完的一方保持合适牌型。建议倾向：本家难以走完时考虑让牌或传递合适牌型，避免无意义盖住队友。反例与调整：危险对手紧急或本家可直接走完时应优先处理更强公开目标。

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

适用条件：对手公开剩余张数很少或其控桌。策略目标：限制强势对手的走牌窗口。建议倾向：把阻断与本家/队友走牌一并比较，而非只看单步压制。反例与调整：不从公开断张推定暗牌；若队友更紧急或本家能走完，可推翻阻断倾向。

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
guidance_mode: source_principle
---

# 炸弹与通配牌管理

适用条件：候选涉及炸弹或逢人配。策略目标：在牌权、阻断和后续结构间保存选择权。建议倾向：显示炸弹长度、通配使用及出后同点孤张，以供模型比较。反例与调整：一次出完、公开紧急对手或规则压制关系可使保留资源不再优先。

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

适用条件：残局或公开剩余张数较少。策略目标：以剩余张数、回手资源和最少分组规划走牌。建议倾向：优先核对一次出完与动作后的估计分组。反例与调整：剩余张数口诀只是信息不足时参考，牌权、炸弹和搭档送牌可推翻。

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

适用条件：需要记牌或试探。策略目标：以公开历史降低不确定性而不虚构暗牌。建议倾向：优先关注王、级牌、A、10、5和公开断张，低成本试探应保留后续路线。反例与调整：10/5及断张只是软信号，不能升级为炸弹或持牌事实。

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
---

# 可撤回的对子试探假设

适用条件：公开信息不足且存在对子候选。策略目标：以较低成本观察和保留多条后续路线。建议倾向：对子可作为侦察/控制候选，小对子有时可留作三带二，并通常避免无谓破坏炸弹或强组顺子。反例与调整：这只是可撤回软假设；具名原则、规则真值、公开紧急性或更小结构损失均可推翻。
