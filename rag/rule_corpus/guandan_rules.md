---
id: rule_single_game_scope_001
corpus: rule
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [scope, legal_actions]
priority: high
keywords_cn: [单局, 范围, 规则真值, 引擎, 合法动作]
---

# 单局规则边界

当前项目只处理单局掼蛋核心规则闭环，不包含多局升级、贡还、比赛长局或地方扩展规则。engine/ 是规则真值，RAG 只说明当前项目规则口径，不能替代 engine.legal_actions()，也不能让模型构造候选列表之外的动作。

---
id: rule_ai_legal_action_id_001
corpus: rule
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [legal_actions, action_id]
priority: high
keywords_cn: [action_id, 合法动作, 候选动作, 不能构造]
---

# AI 只能选择候选 action_id

AI 层只能从 observe() 与 legal_actions() 的公开 payload 中读取信息，并返回 legal_actions 中已有的 action_id。RAG 不生成动作、不修正牌型、不裁决合法性；DeepSeek 输出后仍必须按原始 legal_actions 校验 action_id。

---
id: rule_wildcard_boundary_001
corpus: rule
scene: [lead_opening, lead, follow_response, endgame, any]
phase: [any]
hand_strength: [any]
action_context: [free_lead, follow, endgame, any]
topic: [wildcard, legal_actions]
priority: high
keywords_cn: [逢人配, 红桃级牌, 通配, 替代, wildcard]
---

# 逢人配规则边界

逢人配是红桃级牌。它按自身点数使用时仍是级牌；声明替代时，可替代除大小王以外的特定牌，并按声明后的牌参与比较。一手动作中最多使用一张逢人配。具体能否使用逢人配以及声明为何种牌，必须以 legal_actions 中展开的 declared_cards、carrier_cards、wildcard_count、wildcard_info 为准。

---
id: rule_joker_whitelist_001
corpus: rule
scene: [any]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [joker, joker_bomb, legal_actions]
priority: high
keywords_cn: [王, 大王, 小王, 王炸, 天王炸, 白名单]
---

# 王类牌型白名单

王类牌只允许出现在单张王、王对子、天王炸这类项目已实现牌型中。其他未定义的王类组合不能由模型自行推断为合法牌型。是否存在王类动作，必须以 legal_actions 展开的候选动作为准。

---
id: rule_straight_boundary_001
corpus: rule
scene: [lead_opening, lead, follow_response]
phase: [any]
hand_strength: [any]
action_context: [any]
topic: [straight, pair_straight, steel_plate]
priority: high
keywords_cn: [顺子, 连对, 钢板, A2345, 23456, 10JQKA, JQKA2]
---

# 顺子与连续牌边界

普通顺子固定 5 张；A 可大可小，当前项目允许 A2345、23456、10JQKA，不允许 JQKA2。连对固定 3 对，钢板固定两组三张。逢人配可以参与顺子、连对、钢板和同花顺，但不能突破这些牌型本身的长度、连续性与边界。

---
id: rule_bomb_hierarchy_001
corpus: rule
scene: [follow_response, any]
phase: [any]
hand_strength: [any]
action_context: [follow, any]
topic: [bomb, straight_flush, joker_bomb, control]
priority: high
keywords_cn: [炸弹, 跨型压制, 层级, 长度, 点数]
---

# 炸弹层级

炸弹属于跨型压制资源。当前项目的压制层级为：天王炸高于 6 张及以上炸弹，6 张及以上炸弹高于同花顺，同花顺高于 5 张炸弹，5 张炸弹高于 4 张炸弹。同为炸弹时优先比较长度，长度相同再比较点数。具体可压动作必须以 legal_actions 为准。

---
id: rule_straight_flush_001
corpus: rule
scene: [lead_opening, lead, follow_response]
phase: [any]
hand_strength: [any]
action_context: [free_lead, follow, any]
topic: [straight_flush, bomb, control]
priority: high
keywords_cn: [同花顺, 炸弹层级, 跨型压制]
---

# 同花顺规则位置

同花顺固定 5 张，必须同花，顺子边界与普通顺子一致。逢人配可以参与同花顺，但仍不能突破长度、同花和连续性限制。同花顺在压制层级中位于 6 张及以上炸弹之下、5 张炸弹之上。

---
id: rule_joker_bomb_001
corpus: rule
scene: [follow_response, any]
phase: [any]
hand_strength: [any]
action_context: [follow, any]
topic: [joker_bomb, bomb, control]
priority: high
keywords_cn: [天王炸, 王炸, 最高层级, 四王]
---

# 天王炸

天王炸由两张大王和两张小王组成，是当前项目最高层级的跨型压制牌型。其他王类四张组合不等同于天王炸。是否可出天王炸只看 legal_actions 是否给出对应 action_id。

---
id: rule_pass_follow_001
corpus: rule
scene: [follow_response]
phase: [any]
hand_strength: [any]
action_context: [follow]
topic: [pass, follow_response]
priority: high
keywords_cn: [pass, 过牌, 跟牌, 压制]
---

# pass 规则

在跟牌场景中，如果不选择 legal_actions 中的可压制动作，可以选择 pass。pass 只表示本次不压，不改变桌面牌型合法性。pass 是否可选必须以 legal_actions 为准，RAG 不能额外允许或禁止 pass。

---
id: rule_follow_response_001
corpus: rule
scene: [follow_response]
phase: [any]
hand_strength: [any]
action_context: [follow]
topic: [follow_response, bomb, pass]
priority: high
keywords_cn: [跟牌, 同型压制, 跨型压制, pass]
---

# 跟牌压制规则

跟牌只能使用同型更大的牌压制，或使用炸弹、同花顺、天王炸进行跨型压制；否则只能 pass。模型不得根据经验自行认定某个未出现在 legal_actions 中的牌组可以压制。

---
id: rule_receiving_lead_001
corpus: rule
scene: [lead, any]
phase: [midgame, endgame, any]
hand_strength: [any]
action_context: [free_lead, any]
topic: [receiving_lead, teammate_support]
priority: medium
keywords_cn: [接风, 出牌权, 队友, 无人可压]
---

# 接风

某玩家出完最后一手牌后，先确定其名次；若该玩家不是三游，游戏继续。若仍在局中的玩家无人可压制，则其队友获得下一轮出牌权。已出完牌的玩家不再参与后续轮转与跟牌。

---
id: rule_third_finish_endgame_001
corpus: rule
scene: [endgame]
phase: [endgame]
hand_strength: [any]
action_context: [endgame]
topic: [endgame, run_out, finish_order]
priority: high
keywords_cn: [三游, 终局, 末游, 名次, 结束]
---

# 三游终局

当第三个玩家出完手牌并成为三游时，整局结束；唯一仍未出完牌的玩家自动判定为末游。终局与名次判定由 engine/ 推进，RAG 只能说明该规则口径。
