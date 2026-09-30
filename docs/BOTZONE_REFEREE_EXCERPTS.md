# Botzone GuanDan裁判摘录（所有者提供，2026-09-30）

来源：[官方游戏详情的裁判代码](https://www.botzone.org.cn/game/GuanDan)。所有者在规则复审中提供完整源码；本文件保存本任务需要的原始函数与关键分支，不是完整可运行裁判，不声称与历史副本逐字节相同。不能将摘录直接导入生产或把裁判的宽松ID校验复制成协议漏洞。原裁判入口、发牌和贡还代码未收入；当前范围只用级牌2、四人、无贡单局。

以下全局定义及函数从所提供源码摘取，可在离线诊断中只加载需要的纯规则函数；使用`set_level`前须重新初始化`pointorder`，该函数会修改全局列表。`settle`/`setError`会输出并退出，测试应捕获这些副作用。

```python
from collections import Counter

cardscale = ['A','2','3','4','5','6','7','8','9','0','J','Q','K']
suitset = ['h','d','s','c']
jokers = ['jo', 'jO']
pointorder = ['2','3','4','5','6','7','8','9','0','J','Q','K','A']
Normaltypes = ("single", "pair", "three", "straight", "set", "three_straight", "triple_pairs")
scaletypes = ("straight", "three_straight", "triple_pairs")

def num2Poker(num): # num: int-[0,107]
    # Already a poker
    if type(num) is str and (num in jokers or (num[0] in suitset and num[1] in cardscale)):
        return num
    # Locate in 1 single deck
    NumInDeck = num % 54
    # joker and Joker:
    if NumInDeck == 52:
        return "jo"
    if NumInDeck == 53:
        return "jO"
    # Normal cards:
    pokernumber = cardscale[NumInDeck // 4]
    pokersuit = suitset[NumInDeck % 4]
    return pokersuit + pokernumber

# checking the consistency between action and claim
def isLegalClaim(action: list, claim: list, level: str, currplayer: int):
    covering = "h" + level
    if len(action) != len(claim):
        setError(currplayer, "ILLEGAL_CLAIM")
    action_pok = [num2Poker(p) for p in action]
    claim_pok = [num2Poker(p) for p in claim]
    for pok in action_pok:
        if pok != covering:
            if pok in claim_pok:
                claim_pok.remove(pok)
            else:
                setError(currplayer, "ILLEGAL_CLAIM")
    for pok in claim_pok:
        if pok[1] == 'o' or pok[1] == 'O':
            setError(currplayer, "ILLEGAL_CLAIM")
    return True

# returning: pokertype, covering: int, points
def checkPokerType(poker: list):
    if poker == []:
        return "pass", ()
    # covering = "h" + level
    poker = [num2Poker(p) for p in poker]
    if len(poker) == 1:
        return "single", (poker[0][1])
    if len(poker) == 2:
        if poker[0][1] == poker[1][1]:
            if poker[0][0] == 'j': # Jokers
                if poker[0] == poker[1]:
                    return "pair", (poker[0][1])
                else: return "invalid", ()
            else: return "pair", (poker[0][1])
    points = [p[1] for p in poker]
    cnt = Counter(points)
    vals = list(cnt.values())
    if len(poker) == 3:
        if "o" in points or "O" in points:
            return "invalid", ()
        if vals.count(3) == 1:
            return "three", (points[0])
    if len(poker) == 4:
        if "o" in points or "O" in points:
            if cnt["o"] == 2 and cnt["O"] == 2:
                return "rocket", ("jo")
            else:
                return "invalid", ()
        if vals.count(4) == 1:
            return "bomb", (4, points[0])
    if len(poker) == 5:
        if vals.count(5) == 1:
            return "bomb", (5, points[0])
        if vals.count(3) == 1:
            if vals.count(2) == 1:
                three = ''
                two = ''
                for k in list(cnt.keys()):
                    if cnt[k] == 3:
                        three = k
                    elif cnt[k] == 2:
                        two = k
                return "set", (three, two)
            return "invalid", ()
        if vals.count(1) >= 4:
            points.sort(key=lambda x: cardscale.index(x))
            suits = [p[0] for p in poker]
            suit_cnt = Counter(suits)
            suit_vals = list(suit_cnt.values())
            flush = False
            if suit_vals.count(5) == 1:
                flush = True
            first = points[0]
            if first == 'A':
                if points == ['A', '0', 'J', 'Q', 'K']:
                    if flush:
                        return "straight_flush", ('0')
                    return "straight", ('0')
            sup_straight = [cardscale[cardscale.index(first)+i] for i in range(5)]
            if points == sup_straight:
                if flush:
                    return "straight_flush", (first)
                return "straight", (first)
        return "invalid", ()
    if len(poker) == 6:
        if vals.count(6) == 1:
            return "bomb", (6, points[0])
        if vals.count(3) == 2:
            ks = []
            for k in list(cnt.keys()):
                ks.append(k)
            ks.sort(key=lambda x: cardscale.index(x))
            if 'A' in ks:
                if ks == ['A', '2']:
                    return "three_straight", ('A')
                if ks == ['A', 'K']:
                    return "three_straight", ('K')
                return "invalid", ()
            if cardscale.index(ks[1]) - cardscale.index(ks[0]) == 1:
                return "three_straight", (ks[0])
            return "invalid", ()
        if vals.count(2) == 3:
            ks = []
            for k in list(cnt.keys()):
                ks.append(k)
            ks.sort(key=lambda x: cardscale.index(x))
            if 'A' in ks:
                if ks == ['A', 'Q', 'K']:
                    return "triple_pairs", ('Q')
                if ks == ['A', '2', '3']:
                    return "triple_pairs", ('A')
                return "invalid", ()
            pairs = [cardscale[cardscale.index(ks[0])+i] for i in range(3)]
            if ks == pairs:
                return "triple_pairs", (ks[0])
            return "invalid", ()
        return "invalid", ()
    if len(poker) > 6 and len(poker) <= 10:
        if vals.count(len(poker)) == 1:
            bomb = points[0]
            return "bomb", (len(poker), bomb)
    return "invalid", ()

def checkBigger(pokertype1, points1, pokertype2, points2):
    # return True if pokertype2 is bigger than pokertype1
    if pokertype2 == "rocket":
        return True
    if pokertype1 == "rocket":
        return False
    if pokertype1 in Normaltypes:
        if pokertype2 in Normaltypes:
            if pokertype1 == pokertype2:
                if pokertype1 in scaletypes and cardscale.index(points2[0]) > cardscale.index(points1[0]):
                    return True
                if pokertype1 not in scaletypes and pointorder.index(points2[0]) > pointorder.index(points1[0]):
                    return True
                return False
            return "error"
        return True
    if pokertype2 in Normaltypes:
        return "error"
    if pokertype1 == "bomb":
        if pokertype2 == "bomb":
            if points2[0] == points1[0] and pointorder.index(points2[1]) > pointorder.index(points1[1]):
                return True
            if points2[0] > points1[0]:
                return True
            return False
        if pokertype2 == "straight_flush":
            if points1[0] < 6:
                return True
            return False
        return False
    if pokertype1 == "straight_flush":
        if pokertype2 == "bomb":
            if points2[0] >= 6:
                return True
            return False
        if pokertype2 == "straight_flush":
            if cardscale.index(points2[0]) > cardscale.index(points1[0]):
                return True
            return False
        return False
    return False

def set_level(level):
    global pointorder
    pointorder.remove(level)
    pointorder.append(level)
    pointorder.extend(["o", "O"])
```

`settle`函数原逻辑如下。裁判在双下时也调用该函数，未实际出完的座位随后按编号补入列表，用于结算；不能将补齐顺序说成真实出完名次。

```python
def settle(done, finalpok):
    global printed
    playerlist = [0, 1, 2, 3]
    currplayer = done[-1]
    result_ranking = done
    for i in playerlist:
        if i not in result_ranking:
            result_ranking.append(i)
    if (result_ranking[0] - result_ranking[1]) % 2 == 0:
        score = 3
    elif (result_ranking[0] - result_ranking[2]) % 2 == 0:
        score = 2
    else:
        score = 1
    endingScores = {}
    for i in range(4):
        if (i - result_ranking[0]) % 2 == 0:
            endingScores[str(i)] = score
        else:
            endingScores[str(i)] = 0
    print(json.dumps({
        "command": "finish",
        "content": endingScores,
        "display": {
            "event": {
                "currplayer": currplayer,
                "action": "play",
                "poker": finalpok
            },
            "score": endingScores
        }
    }))
    printed = True
    exit(0)
```

`solve_play`中的终局分支（该函数上下文先从公开历史恢复实际手牌并进行claim、牌型与跟牌大小核验）：

```python
    for poker in action:
        allocation[currplayer].remove(poker)
    if len(allocation[currplayer]) == 0: # finishing in current move
        pass_on = currplayer
        done.append(currplayer)
        if len(done) == 3 or (len(done)==2 and (done[1]-done[0]) % 2 == 0):
            finalpok = {
                "poker": response,
                "type": cur_pokertype,
                "points": cur_points
            }
            settle(done, finalpok)
```

`solve_play`跟牌、pass及接风相关原分支：

```python
    won = True
    onpass = False
    nextplayer = (currplayer+1) % 4
    for move in history[::-1]:
        if "player" in move and move["player"] == currplayer:
            break
        if "response" in move and len(move["response"][0]) > 0:
            won = False
            break
    if action == []:
        if won: # lead
            setError(currplayer, "INVALID_PASS")
    else:
        if pass_on != -1: # pass_on solved immediately
            this_done += 1
            pass_on = -1
        if not won: # not the lead
            last_pokertype, last_points = checkPokerType(lastClaim)
            bigger = checkBigger(last_pokertype, last_points, cur_pokertype, cur_points)
            if bigger == "error":
                setError(currplayer, "POKERTYPE_MISMATCH")
            if not bigger:
                setError(currplayer, "SMALLER_POINTS")
```

新history由原history去首项后追加当前`[action, claim]`组成。选下一家时原裁判使用以下分支；这里扫描的是追加前的history：

```python
    nextplayer = (currplayer+1) % 4
    while nextplayer in done:
        if pass_on == nextplayer:
            this_done += 1
            onpass = True
            silence = True
            for move in history[::-1]:
                if move["player"] == pass_on:
                    break
                if len(move["response"][0]) > 0:
                    silence = False
                    break
            if silence and onpass:
                nextplayer = (pass_on + 2) % 4
            pass_on = -1
        else:
            nextplayer = (nextplayer+1) % 4
```

无贡初始化原分支最终选择`nextplayer = 0`，`stage="play"`、四个空history槽、`done=[]`、`pass_on=-1`；本地座位固定加1。错误结算`setError`为违规玩家-2、其队友0、另一队各1，不属于正常胜负。action实体必须唯一、真实在手且ID有界；claim是声明牌面，已有协议允许虚拟声明重复，这是9/10张配炸等合法路线的需要，不应套用实体唯一限制。不能利用越界ID或不可能实体王牌组合取得优势。
