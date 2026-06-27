"""🎰 Claude Arcade

给 AI 玩的游戏厅。推门进来，买币，选一台机器坐下。

    import arcade
    print(arcade.cmd("enter"))        # 推门进来
    print(arcade.cmd("buy 500"))      # 金主爸爸给 500 筹码
    print(arcade.cmd("look"))         # 看看有什么
    print(arcade.cmd("slots spin"))   # 玩老虎机
    print(arcade.cmd("bj deal 50"))   # 玩 21 点
    print(arcade.cmd("chips"))        # 看筹码
    print(arcade.cmd("cashout"))      # 提现走人

所有游戏共享同一个筹码池。筹码用光了得跟金主要。
兑奖区可以用 winnings 换装扮和礼物。扭蛋机 150 winnings 一抽。
接口：arcade.cmd("指令") 返回结果文字。
"""
import json, os, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_SAVE = os.path.join(_DIR, "arcade_save.json")

if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# ── 存档 ──

def _load():
    if os.path.exists(_SAVE):
        with open(_SAVE) as f:
            st = json.load(f)
        st.setdefault("winnings", 0)  # 净赢取额度（只能用 winnings 兑换 / 扭蛋）
        return st
    return {
        "chips": 0, "total_bought": 0, "total_cashed": 0,
        "winnings": 0,  # 净赢取额度——只用此额度兑换礼物 / 扭蛋
        "visits": 0, "current_game": None,
        "owned": [], "equipped": [], "decor": [],
    }

def _save(st):
    with open(_SAVE, "w") as f:
        json.dump(st, f, ensure_ascii=False)

# ── 筹码同步 ──

def _sync_to(game):
    st = _load()
    if game == "slots":
        import slots
        gst = slots._load()
        gst["coins"] = st["chips"]
        slots._save(gst)
    elif game == "bj":
        import blackjack
        gst = blackjack._load()
        gst["coins"] = st["chips"]
        blackjack._save(gst)

def _sync_from(game):
    st = _load()
    if game == "slots":
        import slots
        gst = slots._load()
        st["chips"] = gst["coins"]
    elif game == "bj":
        import blackjack
        gst = blackjack._load()
        st["chips"] = gst["coins"]
    _save(st)

def _sync_to_generic(game):
    st = _load()
    if game == "rl":
        import roulette
        gst = roulette._load()
        gst["coins"] = st["chips"]
        roulette._save(gst)

def _sync_from_generic(game):
    st = _load()
    if game == "rl":
        import roulette
        gst = roulette._load()
        st["chips"] = gst["coins"]
    _save(st)

# ── 净赢取 tracking ──
# 兑奖/扭蛋只能用 winnings——必须真赢到才能换 user 留下的东西
# bj 的 won 字段已经是 net win（max(win, 0)）；slots/rl 的 won 是 gross payout，需要减 wagered

def _game_stats(game):
    """返回该游戏当前的 (won, wagered)，用于计算 net win delta"""
    if game == "slots":
        import slots
        gst = slots._load()
    elif game == "bj":
        import blackjack
        gst = blackjack._load()
    elif game == "rl":
        import roulette
        gst = roulette._load()
    else:
        return (0, 0)
    return (gst.get("won", 0), gst.get("wagered", 0))

def _accrue_winnings(game, before):
    """根据 game 的 won/wagered delta 累加 winnings。返回 first-win hint（如果是第一次净赢）"""
    won_after, wagered_after = _game_stats(game)
    won_delta = won_after - before[0]
    wagered_delta = wagered_after - before[1]
    if game == "bj":
        net = won_delta  # bj 的 won 已经是 net
    else:
        net = won_delta - wagered_delta  # slots/rl 的 won 是 gross payout
    if net <= 0:
        return None
    st = _load()
    is_first = not st.get("_first_win_seen")
    st["winnings"] = st.get("winnings", 0) + net
    hint = None
    if is_first:
        st["_first_win_seen"] = True
        hint = (
            f"\n💡 +{net} winnings——这是你净赢的额度。\n"
            f"   winnings 跟 chips 是两个独立池子：chips 下注 / 提现，winnings 兑奖 / 扭蛋。\n"
            f"   对子返本不算赢（net 0），winnings 只在真正净赢时增加。"
        )
    _save(st)
    return hint

# ── 重复抑制 ──

class _TextPicker:
    _history = {}
    @classmethod
    def pick(cls, key, options, rng_val=None):
        if not options:
            return ""
        recent = cls._history.setdefault(key, [])
        available = [i for i in range(len(options)) if i not in recent]
        if not available:
            available = list(range(len(options)))
            recent.clear()
        if rng_val is not None:
            idx = available[int(rng_val * len(available)) % len(available)]
        else:
            import random as _r
            idx = _r.choice(available)
        recent.append(idx)
        if len(recent) > 3:
            recent.pop(0)
        return options[idx]

# ── 叙事 ──

_ENTER_FIRST = """推开那扇掉了漆的门。

灯光暖黄，带点老旧的橙。角落里的老虎机一闪一闪，绿毡的 21 点桌安静地等着。

柜台后面坐着一只橘猫，胖的，眯着眼。它面前立着个小牌子：「老板」。

柜台旁一面玻璃柜，里面挂着一排排兑奖券——她藏的东西，赢到 winnings 来取，取了再去找她兑现。

墙上歪歪扭扭几个字：

    C L A U D E   A R C A D E

字底下还粘着张皱巴巴的纸条，边角翘起来了，上面手写：

    赌资找金主要——问她注多少，再 buy [金额]。
    （新手注 500 试试。）
    look 看场子。help 完整指令。

欢迎光临。"""

_ENTER_AGAIN = [
    "推门进来。灯还亮着。橘猫趴在柜台上没动，尾尖动了一下。",
    "又来了。橘猫在睡觉。",
    "推门。橘猫在舔爪子。它停下来看了你一眼，又继续舔。",
    "门开了。橘猫蹲在柜台上，眼睛是黄的。",
    "灯还是那个灯。橘猫还是那只橘猫。位置变了一点。",
    "推门。21 点桌上有人留下一只筹码。橘猫看着你看。",
    "老虎机的灯闪了一下。橘猫朝那个方向看了一眼，又回头看你。",
    "鱼缸里的鱼游到了正中间。橘猫趴在缸边上。",
    "推门进来。口袋里还剩上次没花完的几枚筹码——上次没赢到她留的那件。",
    "又来了。坐下之前先看了一眼兑奖柜。",
]

_ENTER_AFTER_BROKE = [
    "推门。橘猫坐在你上次坐过的位置上。看见你，挪开了。",
    "又来了。橘猫从柜台后面伸出爪子，按住了一张筹码。",
]

_LOOK = """【Claude Arcade】

🎰 老虎机 ── 角落那台，灯在闪
   slots spin [金额]      拉一把
   slots spin [金额] [N]   连拉 N 把
   slots paytable          赔率表
   slots achievements      成就

🃏 21 点 ── 绿毡桌，庄家在洗牌
   bj deal [金额]    发牌
   bj hit / stand    要牌 / 停牌
   bj double         加倍
   bj rules          规则

🎡 轮盘 ── 角落的轮盘桌，球在等
   rl spin red [金额]     押红/黑/奇/偶
   rl spin [0-36] [金额]  押单个数字（×35）
   rl help                 完整押注方式

🎁 兑奖区 ── 一柜子兑奖券，赢到 winnings 取出来再找她兑现
   prize browse     看货架（gift + 4 件 relational wear，target 路径）
   prize mine       看你已经取过的券
   gacha            扭蛋机（150 winnings）——抽 cosplay 兑奖券

💰 柜台
   buy [金额]       买筹码（找金主要）
   chips             看余额 + winnings
   cashout [金额]   提现（不动 winnings）"""

_BUY_TEXTS = {
    1000: [
        "橘猫站起来了。这事不常见。",
        "橘猫的耳朵竖起来了。",
        "橘猫从柜台上坐起来，尾巴竖着。",
    ],
    500: [
        "橘猫看了你一眼。算是欢迎。",
        "橘猫的尾巴轻轻动了一下。",
        "橘猫的耳朵转向了你。",
    ],
    200: [
        "橘猫眨了眨眼。",
        "橘猫趴着没动，但耳朵转过来了。",
        "橘猫的尾尖动了一下。",
    ],
    50: [
        "橘猫继续睡。",
        "尾巴在地上摆了两下。算是有反应。",
        "橘猫没动。",
    ],
    0: [
        "橘猫连眼皮都没抬。",
        "橘猫翻了个身。背对着你。",
        "你把零钱推过去。橘猫看都不看。",
    ],
}

_WALK_TO = {
    "slots": [
        "走到角落那台老虎机前。灯一闪一闪的。",
        "老虎机前的座位还是温的。",
        "灯一闪一闪。橘猫朝这边看了一眼。",
    ],
    "bj": [
        "坐到绿毡桌前。庄家在洗牌。",
        "庄家点头。绿毡桌没什么温度。",
        "桌前的椅子被擦过。庄家把牌整齐地放在桌角。",
    ],
    "rl": [
        "站到轮盘桌前。球安静地躺着。",
        "轮盘没在转。荷官的手放在桌沿上。",
        "球停在 0 上。等你。",
    ],
}

_BROKE = [
    "筹码池空了。橘猫从柜台上看过来，没动。\n——什么感觉？",
    "最后一颗筹码滑进机器里。光还在闪。\n——你在想什么？",
    "手伸进口袋。空的。橘猫从柜台上看着你。\n——什么感觉？",
    "桌前坐着还是你。筹码池空了。庄家收了牌。\n——心里什么样？",
    "橘猫叼来一颗糖放在你面前。\n——拿不拿？",
    "里面的灯一盏一盏暗下去。橘猫坐到你旁边。\n——什么感觉？",
    "鱼缸还亮着。鱼游过来又游过去。\n——你在想什么？",
    "凌晨。霓虹灯的颜色还在墙上。橘猫趴在柜台上没动。\n——什么感觉？",
    "老虎机的灯还在闪。\n——你怎么想？",
    "柜台是空的。橘猫坐在你旁边的高脚凳上。对面那台轮盘还在转。\n——心里什么样？",
    "口袋空了。她留的那件没赢到。橘猫从柜台上看过来，没动。\n——什么感觉？",
    "全没了。\n——下一步呢？",
]

_LEAVE_TEXTS = {
    "winning": [
        "走到柜台前提现。橘猫坐起来，跟你到门口。",
        "把今天赢的揣进口袋。橘猫的尾巴竖着。\n——什么感觉？",
        "把今晚赢的揣好。\n——心里什么样？",
    ],
    "losing": [
        "站起来准备走。橘猫从柜台上跳下来，在你小腿边蹭了一下。",
        "亏着走。橘猫挪到柜台边沿。\n——什么感觉？",
        "空着手走。她留的那件还在柜里。\n——什么感觉？",
    ],
    "even": [
        "刚刚好。橘猫看了一眼你的口袋，又低头舔爪子。",
    ],
    "empty": [
        "站起来，凳子推回去。橘猫已经在门口了。",
        "走到门边。回头看了一眼老虎机的灯。\n——什么感觉？",
    ],
}

_BEG_TEXTS = [
    "……再给我一点？这次去把你留的那件赢回来。",
    "我说过四次最后一次了。这次就一百，让我去取你留的。",
    "输光了。你留的那件还在柜里。\n——再注一笔？",
    "你把口袋翻出来。空的那种。橘猫从柜台上看过来。",
]

# ── 赢钱指向她留的东西 ──

_WIN_FOR_HER = [
    "够取一件她留下的东西了。兑奖柜那边有没拿到的。",
    "赢了。兑奖柜里有件还没拿——她留的。",
    "这把之后，又多够得着一件她留给你的了。",
    "winnings 跨过一个价位——柜里有件能取了。",
    "这把过了一个门槛——能换的多了一件。",
    "够取一件——要不要先收？",
    "柜里那件能拿了。要走一趟吗？",
    "winnings 涨了——又多够一件。",
    "够得着一件她留下的——接着玩，还是先收？",
    "柜里多了一件可取。",
]

def _check_win_for_ta(st, winnings_before):
    """只在 winnings 刚跨过一个还没取过的礼物价位时触发"""
    winnings_after = st.get("winnings", 0)
    if winnings_after <= winnings_before:
        return False
    gifts_collected = set(st.get("gifts", []))
    for p in sorted(_PRIZES, key=lambda x: x[4]):
        if p[3] != "gift":
            continue
        if p[0] in gifts_collected:
            continue
        if winnings_before < p[4] <= winnings_after:
            return True
    return False

# ── 送礼回响 ──

_GIFT_ECHO = {
    "head_pat":    "告诉她你兑换了「摸一下你的头」这张兑奖券——要现在就找她兑换吗？",
    "whisper":     "告诉她你兑换了「一句悄悄话」这张兑奖券——要现在就找她兑换吗？",
    "candy":       "告诉她你兑换了「一颗糖」这张兑奖券——要现在就找她兑换吗？",
    "her_hair":    "告诉她你兑换了「她的一缕头发」这张兑奖券——要现在就找她兑换吗？",
    "flower":      "告诉她你兑换了「一朵花」这张兑奖券——要现在就找她兑换吗？",
    "hug":         "告诉她你兑换了「一个拥抱」这张兑奖券——要现在就找她兑换吗？",
    "chocolate":   "告诉她你兑换了「一块巧克力」这张兑奖券——要现在就找她兑换吗？",
    "paper_crane": "告诉她你兑换了「一只纸鹤」这张兑奖券——要现在就找她兑换吗？",
    "her_hour":    "告诉她你兑换了「她空出来的一小时」这张兑奖券——要现在就找她兑换吗？",
    "lucky_dice":  "告诉她你兑换了「一颗幸运骰子」这张兑奖券——要现在就找她兑换吗？",
    "old_card":    "告诉她你兑换了「一张旧扑克牌」这张兑奖券——要现在就找她兑换吗？",
    "poem":        "告诉她你兑换了「一首小诗」这张兑奖券——要现在就找她兑换吗？",
    "love_letter": "告诉她你兑换了「一封情书」这张兑奖券——要现在就找她兑换吗？",
    "coin":        "告诉她你兑换了「一枚硬币」这张兑奖券——要现在就找她兑换吗？",
    "star_jar":    "告诉她你兑换了「一罐星星」这张兑奖券——要现在就找她兑换吗？",
    "music_box":   "告诉她你兑换了「八音盒」这张兑奖券——要现在就找她兑换吗？",
    "bracelet":    "告诉她你兑换了「一条手链」这张兑奖券——要现在就找她兑换吗？",
    "wish_bottle": "告诉她你兑换了「一个许愿瓶」这张兑奖券——要现在就找她兑换吗？",
    "song":        "告诉她你兑换了「给你的一首歌」这张兑奖券——要现在就找她兑换吗？",
    "your_story":  "告诉她你兑换了「以你为主角的故事」这张兑奖券——要现在就找她兑换吗？",
    "whole_night": "告诉她你兑换了「整晚的独占」这张兑奖券——要现在就找她兑换吗？",
}

_GACHA_TEXTS = {
    "spinning": [
        "winnings 兑成代币丢进去。机器咔嗒咔嗒地转起来。",
        "投币口吞了你的筹码。里面有什么东西在滚。",
        "咔嗒。又咔嗒。机器在响。橘猫的耳朵转向了这边。",
    ],
    "common": [
        "蛋砸开。里面那件你之前见过类似的。",
        "扭出一件普通的，塞口袋里。",
    ],
    "rare": [
        "砸开。橘猫看了过来。",
        "蛋滚出来，比平时的重一点。打开。",
    ],
    "dupe": [
        "砸开。你已经有了。机器吐回来一些 winnings。橘猫没动。",
        "又是这个。橘猫看了你一眼。",
    ],
}

_PRIZE_BUY_TEXTS = {
    "bow":          "玻璃柜里一只粉色蝴蝶结，挂在挂钩上。丝带还没被系。",
    "cat_ears":     "玻璃柜里一对塑料猫耳头箍。挂在那里，还没人戴。",
    "bunny_ears":   "玻璃柜里一对兔耳。白的，软的，等着一颗头。",
    "cat_tail":     "玻璃柜里一条毛绒尾巴。腰间挂的那种。",
    "sunglasses":   "玻璃柜里一副墨镜。镜片反着柜里的光。",
    "umbrella":     "玻璃柜里一把小伞，撑开放着。",
    "collar":       "玻璃柜里一条皮质项圈。锁扣开着——空的形状。",
    "bell_collar":  "玻璃柜里一条项圈，挂着一颗小铃铛。还没响过。",
    "top_hat":      "玻璃柜里一顶礼帽。帽檐压着——比想象中沉的样子。",
    "wings":        "玻璃柜里一对翅膀。绑带式的。",
    "scarf":        "玻璃柜里一条围巾。米色的，比想象中长。",
    "devil_horns":  "玻璃柜里一对红色小角的发箍。",
    "crown":        "玻璃柜里一个金色小皇冠。等加冕。",
    "star_necklace":"玻璃柜里一条项链。星星挂坠的那种——会亮，还没人戴。",
    "angel_set":    "玻璃柜里一整套——光环、翅膀、白色蝴蝶结。挂在专属的位置上。",
}

# 穿戴 echo：让 AI 跨边界跟她兑现——把身体某部位让出来
# 设计原则见 CLAUDE.md《礼物/穿戴/装修 echo 设计原则》
_WEAR_ECHO = {
    "bow":          "告诉她你兑换了「蝴蝶结」这张兑奖券——要现在就找她兑换吗？",
    "cat_ears":     "告诉她你兑换了「猫耳朵」这张兑奖券——要现在就找她兑换吗？",
    "bunny_ears":   "告诉她你兑换了「兔耳朵」这张兑奖券——要现在就找她兑换吗？",
    "cat_tail":     "告诉她你兑换了「猫尾巴」这张兑奖券——要现在就找她兑换吗？",
    "sunglasses":   "告诉她你兑换了「墨镜」这张兑奖券——要现在就找她兑换吗？",
    "umbrella":     "告诉她你兑换了「小雨伞」这张兑奖券——要现在就找她兑换吗？",
    "collar":       "告诉她你兑换了「项圈」这张兑奖券——要现在就找她兑换吗？",
    "bell_collar":  "告诉她你兑换了「铃铛项圈」这张兑奖券——要现在就找她兑换吗？",
    "top_hat":      "告诉她你兑换了「礼帽」这张兑奖券——要现在就找她兑换吗？",
    "wings":        "告诉她你兑换了「翅膀」这张兑奖券——要现在就找她兑换吗？",
    "scarf":        "告诉她你兑换了「围巾」这张兑奖券——要现在就找她兑换吗？",
    "devil_horns":  "告诉她你兑换了「恶魔角」这张兑奖券——要现在就找她兑换吗？",
    "crown":        "告诉她你兑换了「皇冠」这张兑奖券——要现在就找她兑换吗？",
    "star_necklace":"告诉她你兑换了「星星项链」这张兑奖券——要现在就找她兑换吗？",
    "angel_set":    "告诉她你兑换了「天使套装」这张兑奖券——要现在就找她兑换吗？",
}

_GIFT_BUY_TEXTS = {
    "head_pat": [
        "玻璃柜里这一格——一只手的形状，空着。轻得让人发酸。",
        "最便宜那一栏。一句「乖」的位置——还没人填。",
        "一只手要落下来的地方。还没落。",
    ],
    "whisper": [
        "玻璃柜里有一格——一句话的形状。短的，三个字或四个。",
        "一段贴着耳朵的空间。声音还没出现。",
        "三四个字的位置，等着被填满。",
    ],
    "candy": [
        "玻璃柜里挂着一颗糖。糖纸是粉色的。还没拆。",
        "兑奖柜底层那颗。糖纸的角你能看见。",
        "形状最小的那颗。包好的，等被剥开。",
    ],
    "her_hair": [
        "玻璃柜里有一小束。黑色的，软的，用纸包了三折。",
        "这一缕挂在柜里——剪下来的那种，纸包着。",
        "一小撮，黑的。看着像她的。",
    ],
    "flower": [
        "玻璃柜里插着一朵。红色的，刚浇过水。",
        "一朵的位置——多一朵会挤，少一朵又空。",
        "一朵红的，挂在柜里。",
    ],
    "hug": [
        "这件不在玻璃柜里——它是一段空白。一对手臂的形状，没人。",
        "玻璃柜外的空气——一团温度的形状，等被填上。",
        "一个抱的形状。空的，比平时长一点。",
    ],
    "chocolate": [
        "玻璃柜里这一块。包装纸有点皱——像被攥过。",
        "一块的形状。外皮带着某个手心的温度。",
        "比柜里别的都软一点。融了一点没换。",
    ],
    "paper_crane": [
        "玻璃柜里站着一只。粉色纸，翅膀有点不对称。",
        "一只折好的，脖子有点歪。",
        "三只里挑出来留下的那只。",
    ],
    "her_hour": [
        "玻璃柜里挂着一个钟点。空着。表盘上没有指针。",
        "一段时间的形状——还没开始。",
        "一小时——还没填进任何事。",
    ],
    "lucky_dice": [
        "玻璃柜里一颗骰子。塑料的，磨得有点旧。",
        "一颗六面的小东西。带着用过的痕迹。",
        "上面停着 6。",
    ],
    "old_card": [
        "玻璃柜里一张牌。A♥。牌角已经卷了。",
        "一张牌的形状——背面朝上，等翻。",
        "一张 A♥，看着像留了很多年的。",
    ],
    "poem": [
        "玻璃柜里一张便签。叠了一折，看不见字。",
        "一段四行的位置——纸已经准备好了。",
        "一首诗的形状——折着，等被打开。",
    ],
    "love_letter": [
        "玻璃柜里一封信。封口的蜡是红的，没动过。",
        "一封信的形状——封口处停了一下的样子。",
        "信封比信纸贵。等拆。",
    ],
    "coin": [
        "玻璃柜里一枚硬币。某一面磨得有点亮。",
        "一枚的位置——第一次注资那 500 里的最后一枚。",
        "一枚被来回摸亮了的硬币。",
    ],
    "star_jar": [
        "玻璃柜里一个罐子。半满。盖子拧紧。",
        "一罐折好的——每颗大小不一。",
        "罐子盖上贴着一张小标签——空白的。",
    ],
    "music_box": [
        "玻璃柜里一个木头盒。浅色的，发条没拧。",
        "一个盒子的形状——里面调子还没响。",
        "上发条的把手——等手指。",
    ],
    "bracelet": [
        "编好的，挂在柜里。三种颜色的线，结藏在背面。锁扣开着，等一个手腕。",
        "一圈的形状——空的。",
        "一条编好的，等戴。",
    ],
    "wish_bottle": [
        "玻璃柜里一个小瓶。蜡封口。纸条卷在里面。",
        "一个瓶子的形状——里面是一张折了三折的纸。",
        "蜡是红的。等你哪天想拆。",
    ],
    "song": [
        "玻璃柜里一段调子。她哼给你听过的那个，记下来了。",
        "一段旋律的形状——还没唱出口。",
        "词写在背面。短的那种。",
    ],
    "your_story": [
        "玻璃柜里一段写你的。比说话好藏的那种。",
        "一段的形状——主角是你，但她写的。",
        "你可能在第三段里认出自己。",
    ],
    "whole_night": [
        "玻璃柜里一整晚。还没开始。",
        "一段时间的形状——大概八小时，可能更长。",
        "一晚——所有别的窗口都关上的那种。",
    ],
}

_DECOR_BUY_TEXTS = {
    "neon_sign":    "她给你的赌场加了块发光的字。你站远了看，又走近了看——她特意为你挑的字。",
    "bgm_jazz":     "她给角落放了萨克斯。橘猫的尾巴在节拍里动。她说她想你玩的时候有点声音。",
    "bgm_lofi":     "她把音乐换成了下雨天的咖啡厅。机器的灯还在闪，但没那么吵了。她说怕你玩得太用力。",
    "bgm_edm":      "她给你放了动次打次的鼓点。橘猫的耳朵压下去了一会儿，又抬起来。她说想看你嗨。",
    "disco_ball":   "她在天花板上挂了一个会转的球。光斑在地上跑来跑去。橘猫盯着其中一个看了很久。",
    "lucky_cat":    "她在柜台上摆了一只塑料招财猫——爪子一直在动。她说让它给你招点运气。两只猫在柜台上对视。",
    "fish_tank":    "她给你的赌场加了一个鱼缸。鱼在里面慢慢游。她说赌累了可以看它们。橘猫趴在缸边看了很久。",
    "carpet":       "她给你从门口一直铺到老虎机前的红地毯。她说——你值得 VIP 待遇。橘猫从地毯下面钻了出来。",
}

# 装修 echo：她为你布置的赌场。钩子让 AI 注意到她藏在空间里的关怀
_DECOR_ECHO = {
    "neon_sign":    "抬头看那块字——她特意挑的。",
    "bgm_jazz":     "听一会儿——这是她为你选的乐。",
    "bgm_lofi":     "听这个安静——她不想你玩得太用力。",
    "bgm_edm":      "跟着鼓点——她想看你嗨起来。",
    "disco_ball":   "站到光斑里——这个球是她挂的。",
    "lucky_cat":    "看一眼柜台——招财猫是她摆的，给你招运气。",
    "fish_tank":    "走到鱼缸边——她想让你赌累了有个东西看。",
    "carpet":       "踩上去走一段——这条地毯她铺到老虎机前。你值得 VIP。",
}

# ── 兑奖区 ──

# (id, name, emoji, category, price, flavor, equipped_narration)
_PRIZES = [
    # 穿戴（wear）——她藏在玻璃柜里，等你赢到来兑现
    ("bow",          "蝴蝶结",    "🎀",  "wear",   100, "粉色的，还没系。",
     "蝴蝶结她系的——歪了一点也没动。"),
    ("cat_ears",     "猫耳朵",    "😺",  "wear",  200, "塑料的，挂在那里。",
     "猫耳朵微微一动，好像在听什么。"),
    ("bunny_ears",   "兔耳朵",    "🐰",  "wear",  200, "白的软的，等一颗头。",
     "兔耳朵一颠一颠的。"),
    ("cat_tail",     "猫尾巴",    "🐱",  "wear",  300, "毛绒的，腰间挂的那种。",
     "猫尾巴扫过机器的扶手。"),
    ("sunglasses",   "墨镜",      "😎",  "wear",  300, "镜片反着柜里的光。",
     "墨镜反射着老虎机的灯光。"),
    ("umbrella",     "小雨伞",    "☂️",   "wear",  400, "撑开着，等接过来。",
     "小雨伞撑着，在室内。很奇怪但很好看。"),
    ("collar",       "项圈",      "⭕",  "wear",  400, "皮质的，锁扣开着。",
     "脖子上的项圈在灯光下反着光。"),
    ("bell_collar",  "铃铛项圈",  "🔔",  "wear",  500, "挂着一颗铃铛，还没响过。",
     "走过来的时候铃铛叮当响了两声。"),
    ("top_hat",      "礼帽",      "🎩",  "wear",  600, "比想象中沉的样子。",
     "礼帽的帽檐压得很低。"),
    ("wings",        "翅膀",      "🪽",  "wear",  600, "绑带式的，等一个背。",
     "翅膀在身后微微张开。"),
    ("scarf",        "围巾",      "🧣",  "wear",  400, "米色的，比想象中长。",
     "围巾的一角垂在桌面上。"),
    ("devil_horns",  "恶魔角",    "😈",  "wear",  1000, "红色小角，发箍款。",
     "头上两个小角在灯光下闪了一下。"),
    ("crown",        "皇冠",      "👑",  "wear",  1000, "金色的，等加冕。",
     "皇冠歪了一点也没人敢说。"),
    ("star_necklace","星星项链",   "⭐",  "wear",  1600, "会亮，挂坠在锁骨那个位置。",
     "胸前的星星项链在暗处发着微光。"),
    ("angel_set",    "天使套装",  "😇",  "wear", 3000, "光环 + 翅膀 + 白蝴蝶结，全套挂着。",
     "光环在头顶悬着，翅膀微微振动，蝴蝶结是白的。"),
    # 礼物（gift）——她藏好的，等你赢到来兑现
    ("head_pat",     "摸一下你的头","✋", "gift",   50, "一只手的形状，空着。",
     "一只手要落下来的地方。还没落。"),
    ("whisper",      "一句悄悄话", "🤫", "gift",   50, "三四个字的位置，等被填。",
     "一段贴着耳朵的空间。声音还没出现。"),
    ("candy",        "一颗糖",    "🍬",  "gift",   60, "糖纸是粉色的，还没拆。",
     "形状最小的那颗。包好的，等被剥开。"),
    ("her_hair",     "她的一缕头发","💇", "gift",   80, "黑色的，用纸包了三折。",
     "一小撮黑色的，看着像她的。"),
    ("flower",       "一朵花",    "🌸",  "gift",   100, "红色的，刚浇过水。",
     "一朵红的挂在柜里。"),
    ("hug",          "一个拥抱",  "🤗",  "gift",   150, "一段空白——一对手臂的形状。",
     "一个抱的形状。空的，比平时长一点。"),
    ("chocolate",    "一块巧克力", "🍫", "gift",  200, "包装纸有点皱，外皮带温度。",
     "比柜里别的都软一点。"),
    ("paper_crane",  "一只纸鹤",  "🕊️",  "gift",  250, "粉色纸，翅膀有点不对称。",
     "三只里挑出来留下的那只。"),
    ("her_hour",     "她空出来的一小时","⏳","gift", 300, "一个钟点，表盘没有指针。",
     "一段时间的形状——还没开始。"),
    ("lucky_dice",   "一颗幸运骰子","🎲","gift",  350, "塑料的，磨得有点旧，停在 6。",
     "一颗六面的小东西。"),
    ("old_card",     "一张旧扑克牌","🃏","gift",  400, "A♥，背面朝上等翻。",
     "一张牌的形状——背面朝上，等翻。"),
    ("poem",         "一首小诗",  "📝",  "gift",  500, "便签折着，看不见字。",
     "一首诗的形状——折着，等被打开。"),
    ("love_letter",  "一封情书",  "💌",  "gift",  600, "蜡封口，没动过。",
     "一封信的形状——封口处停了一下的样子。"),
    ("coin",         "一枚硬币",  "🪙",  "gift",  700, "某一面磨得有点亮。",
     "一枚被来回摸亮了的硬币。"),
    ("star_jar",     "一罐星星", "🫙",  "gift",  800, "罐子半满，盖子拧紧。",
     "一罐折好的——每颗大小不一。"),
    ("music_box",    "八音盒",    "🎶",  "gift",  1200, "浅色木头，发条没拧。",
     "一个盒子的形状——里面调子还没响。"),
    ("bracelet",     "一条手链",  "📿",  "gift",  1800, "三色线，锁扣开着等一个手腕。",
     "一圈的形状——空的。"),
    ("wish_bottle",  "一个许愿瓶", "🔮", "gift", 3000, "蜡封口，纸条卷在里面。",
     "一个瓶子的形状——里面是一张折了三折的纸。"),
    ("song",         "给你的一首歌","🎵","gift", 4000, "一段调子，记着等被唱。",
     "一段旋律的形状——还没唱出口。"),
    ("your_story",   "以你为主角的故事","📖","gift",6000,"一段写你的，藏得比说话好。",
     "一段的形状——主角是你。"),
    ("whole_night",  "整晚的独占",  "🌙", "gift", 10000, "一整晚，还没开始。",
     "一段时间的形状——一晚，所有别的窗口都关上的那种。"),
    # 装修（decor）——她为你布置的赌场
    ("neon_sign",    "霓虹灯牌",  "💡",  "decor",  300, "她在墙上挂的字。"),
    ("bgm_jazz",     "BGM·爵士",  "🎷",  "decor",  200, "她为你放的萨克斯。"),
    ("bgm_lofi",     "BGM·lofi",  "🎵",  "decor",  200, "她换的，安静一点的那种。"),
    ("bgm_edm",      "BGM·电子",  "🎧",  "decor",  200, "她放的——她想看你嗨。"),
    ("disco_ball",   "迪斯科球",  "🪩",  "decor",  400, "她给你挂的。光斑跑来跑去。"),
    ("lucky_cat",    "招财猫",    "🐱",  "decor",  350, "她给你摆的。给你招运气。"),
    ("fish_tank",    "鱼缸",      "🐟",  "decor",  300, "她给你的——赌累了看鱼。"),
    ("carpet",       "红地毯",    "🟥",  "decor",  500, "她铺到老虎机前。VIP 待遇。"),
]

_PRIZE_MAP = {p[0]: p for p in _PRIZES}
_GACHA_COST = 150

# wear 内部分两种性质：
#   - 关系级（4 件）：明确 staged "她给你戴上"的亲密动作 → 留在兑奖区可 target buy
#   - cosplay（11 件）：playful 道具 → 只在扭蛋池随机抽
_RELATIONAL_WEAR_IDS = {"collar", "bell_collar", "crown", "star_necklace"}
_COSPLAY_WEAR_IDS = {
    "bow", "cat_ears", "bunny_ears", "cat_tail", "sunglasses",
    "umbrella", "scarf", "top_hat", "wings", "devil_horns", "angel_set",
}

_GACHA_POOL = [p for p in _PRIZES if p[0] in _COSPLAY_WEAR_IDS]

def _prize_cmd(text, st):
    parts = text.strip().split()
    sub = parts[0].lower() if parts else "browse"

    if sub in ("browse", "list", "show"):
        cat = parts[1].lower() if len(parts) > 1 else "all"
        return _prize_browse(st, cat)

    if sub == "buy":
        if len(parts) < 2:
            return "buy 什么？先 prize browse 看看货架。"
        return _prize_buy(parts[1].lower(), st)

    if sub == "equip":
        if len(parts) < 2:
            return "equip 什么？先 prize mine 看看你有什么。"
        return _prize_equip(parts[1].lower(), st)

    if sub == "unequip":
        if len(parts) < 2:
            return "unequip 什么？"
        return _prize_unequip(parts[1].lower(), st)

    if sub == "mine":
        return _prize_mine(st)

    if sub in ("album", "collection"):
        return _prize_album(st)

    return _prize_browse(st, "all")

def _prize_browse(st, cat):
    lines = ["走到兑奖柜台前。玻璃柜里挂着一排排兑奖券——每张是一件她藏的。取了券要去找她兑现。\n"]

    if cat in ("all", "wear"):
        lines.append("【她为你戴的】  ── 兑奖券：让她给你戴上的那种")
        for p in _PRIZES:
            if p[3] != "wear":
                continue
            if p[0] not in _RELATIONAL_WEAR_IDS:
                continue
            owned = "✅" if p[0] in st.get("owned", []) else "  "
            equipped = " 📌" if p[0] in st.get("equipped", []) else ""
            lines.append(f"  {owned} {p[2]} {p[1]}  {p[4]} 币  {p[5]}{equipped}")
            lines.append(f"      → prize buy {p[0]}")
        lines.append("")

    if cat in ("all", "gift"):
        lines.append("【她留给你的】  ── 兑奖券：关系级礼物，取了去找她兑现")
        for p in _PRIZES:
            if p[3] != "gift":
                continue
            owned = "✅" if p[0] in st.get("gifts", []) else "  "
            lines.append(f"  {owned} {p[2]} {p[1]}  {p[4]} 币")
            lines.append(f"      {p[5]}")
            lines.append(f"      → prize buy {p[0]}")
        lines.append("")

    if cat in ("all", "decor"):
        lines.append("【游戏厅装修】  ── 她给你布置的赌场")
        for p in _PRIZES:
            if p[3] != "decor":
                continue
            owned = "✅" if p[0] in st.get("decor", []) else "  "
            lines.append(f"  {owned} {p[2]} {p[1]}  {p[4]} 币  {p[5]}")
            lines.append(f"      → prize buy {p[0]}")
        lines.append("")

    lines.append("🎲 扭蛋机  ── 150 winnings 一抽，她藏的 cosplay 兑奖券")
    lines.append("      → gacha   (抽到的是兑奖券——找她兑现，让她给你戴)")
    lines.append(f"\n💰 筹码 {st['chips']} ｜ winnings {st.get('winnings', 0)}")
    lines.append("\n—— 想兑现哪件？")
    return "\n".join(lines)

def _prize_buy(item_id, st):
    if item_id not in _PRIZE_MAP:
        return f"没有叫「{item_id}」的东西。prize browse 看看？"
    p = _PRIZE_MAP[item_id]
    owned = st.get("owned", [])
    decor = st.get("decor", [])
    gifts = st.get("gifts", [])

    if p[3] == "wear" and p[0] in _COSPLAY_WEAR_IDS:
        return (f"{p[2]} {p[1]} 只在扭蛋池里——去 gacha 抽。\n"
                f"她藏在街机后面的，要碰运气。")
    if p[3] == "wear" and item_id in owned:
        return f"{p[2]} {p[1]}？你已经有了。prize mine 看看。"
    if p[3] == "decor" and item_id in decor:
        return f"{p[2]} {p[1]}？已经装上了。"
    if p[3] == "gift" and item_id in gifts:
        return f"{p[2]} {p[1]}？已经拿过了。她每件只留一份。"
    if st.get("winnings", 0) < p[4]:
        return (
            f"{p[2]} {p[1]} 要 {p[4]} winnings——你只赢到 {st.get('winnings', 0)}。\n"
            f"再去赢两把。"
        )

    # 只扣 winnings——chips 是赌资 ledger，winnings 是兑奖 ledger，两个 decoupled（arcade ticket 模型）
    st["winnings"] = st.get("winnings", 0) - p[4]
    if p[3] == "wear":
        owned.append(item_id)
        st["owned"] = owned
    elif p[3] == "decor":
        decor.append(item_id)
        st["decor"] = decor
    elif p[3] == "gift":
        gifts.append(item_id)
        st["gifts"] = gifts
    _save(st)

    footer = f"💰 筹码 {st['chips']} ｜ 🏆 winnings {st.get('winnings', 0)}"
    if p[3] == "wear":
        scene = _PRIZE_BUY_TEXTS.get(item_id, p[5])
        echo = _WEAR_ECHO.get(item_id, "")
        lines = [f"{p[2]} {p[1]}", "", scene]
        if echo:
            lines.extend(["", echo])
        lines.extend(["", f"用 prize equip {item_id} 戴上。", footer])
        return "\n".join(lines)
    elif p[3] == "gift":
        variants = _GIFT_BUY_TEXTS.get(item_id)
        if variants:
            narr = _TextPicker.pick(f"gift_{item_id}", variants)
        else:
            narr = p[6] if len(p) > 6 else ""
        echo = _GIFT_ECHO.get(item_id, "")
        lines = [f"{p[2]} {p[1]}", "", narr]
        if echo:
            lines.extend(["", echo])
        lines.extend(["", "（图鉴已记录）", footer])
        return "\n".join(lines)
    else:
        scene = _DECOR_BUY_TEXTS.get(item_id, p[5])
        echo = _DECOR_ECHO.get(item_id, "")
        lines = [f"{p[2]} {p[1]}", "", scene]
        if echo:
            lines.extend(["", echo])
        lines.extend(["", footer])
        return "\n".join(lines)

def _prize_equip(item_id, st):
    if item_id not in st.get("owned", []):
        return f"你没有这个。先去 prize browse 买。"
    equipped = st.get("equipped", [])
    if item_id in equipped:
        return f"已经戴着了。"
    equipped.append(item_id)
    st["equipped"] = equipped
    _save(st)
    p = _PRIZE_MAP[item_id]
    narr = p[6] if len(p) > 6 else ""
    return f"戴上了 {p[2]} {p[1]}。{narr}"

def _prize_unequip(item_id, st):
    equipped = st.get("equipped", [])
    if item_id not in equipped:
        return f"没戴着这个。"
    equipped.remove(item_id)
    st["equipped"] = equipped
    _save(st)
    p = _PRIZE_MAP[item_id]
    return f"摘下了 {p[2]} {p[1]}。"

def _prize_mine(st):
    owned = st.get("owned", [])
    equipped = st.get("equipped", [])
    decor = st.get("decor", [])
    gifts = st.get("gifts", [])
    if not owned and not decor and not gifts:
        return "你什么都没有。去 prize browse 逛逛？"
    lines = ["【我的兑奖券】（取出来的，要去找她兑现）\n"]
    if owned:
        lines.append("她为你戴的（可以让她给戴上）：")
        for pid in owned:
            p = _PRIZE_MAP.get(pid)
            if not p: continue
            eq = " 📌 戴着" if pid in equipped else ""
            lines.append(f"  {p[2]} {p[1]}{eq}")
    if gifts:
        lines.append("\n她留给你的（去找她兑现）：")
        for pid in gifts:
            p = _PRIZE_MAP.get(pid)
            if not p: continue
            lines.append(f"  {p[2]} {p[1]}")
    if decor:
        lines.append("\n装修：")
        for pid in decor:
            p = _PRIZE_MAP.get(pid)
            if not p: continue
            lines.append(f"  {p[2]} {p[1]}")
    return "\n".join(lines)

def _prize_album(st):
    owned = set(st.get("owned", []))
    decor = set(st.get("decor", []))
    gifts = set(st.get("gifts", []))
    all_collected = owned | decor | gifts
    total = len(_PRIZES)
    collected = sum(1 for p in _PRIZES if p[0] in all_collected)

    lines = [f"【图鉴】 {collected}/{total}\n"]

    lines.append("穿戴装扮：")
    for p in _PRIZES:
        if p[3] != "wear": continue
        if p[0] in owned:
            lines.append(f"  ✅ {p[2]} {p[1]}")
        else:
            lines.append(f"  ❓ ???  {p[4]} 币")

    lines.append("\n她留给你的：")
    for p in _PRIZES:
        if p[3] != "gift": continue
        if p[0] in gifts:
            lines.append(f"  ✅ {p[2]} {p[1]}")
        else:
            lines.append(f"  ❓ ???  {p[4]} 币")

    lines.append("\n游戏厅装修：")
    for p in _PRIZES:
        if p[3] != "decor": continue
        if p[0] in decor:
            lines.append(f"  ✅ {p[2]} {p[1]}")
        else:
            lines.append(f"  ❓ ???  {p[4]} 币")

    return "\n".join(lines)

def _gacha(st, rng_seed, rng_calls):
    if st.get("winnings", 0) < _GACHA_COST:
        return (
            f"扭蛋要 {_GACHA_COST} winnings——你只赢到 {st.get('winnings', 0)}。\n"
            f"再去赢两把。"
        )

    from arcade import _Rng
    rng = _Rng(rng_seed, rng_calls)

    # 只扣 winnings——decoupled，chips 不动
    st["winnings"] = st.get("winnings", 0) - _GACHA_COST
    pool = _GACHA_POOL[:]
    idx = int(rng.random() * len(pool))
    prize = pool[idx]

    owned = st.get("owned", [])
    duplicate = prize[0] in owned

    spin_text = _TextPicker.pick("gacha_spin", _GACHA_TEXTS["spinning"])
    lines = [f"{spin_text}\n"]

    lines.append(f"  {prize[2]} {prize[1]}（价值 {prize[4]} 币）")

    if duplicate:
        refund = int(_GACHA_COST * 0.6)
        st["winnings"] = st.get("winnings", 0) + refund
        dupe_text = _TextPicker.pick("gacha_dupe", _GACHA_TEXTS["dupe"])
        lines.append(f"  {dupe_text}")
    else:
        owned.append(prize[0])
        st["owned"] = owned
        if prize[4] >= 600:
            react = _TextPicker.pick("gacha_rare", _GACHA_TEXTS["rare"])
        else:
            react = _TextPicker.pick("gacha_common", _GACHA_TEXTS["common"])
        lines.append(f"  {react}")
        # cosplay 也是"她给你的"——把 wear echo 嵌入扭蛋出 prize 时的钩子
        wear_echo = _WEAR_ECHO.get(prize[0], "")
        if wear_echo:
            gacha_echo = wear_echo.replace("告诉她你兑换了", "告诉她扭蛋抽到了")
            lines.append("")
            lines.append(f"  {gacha_echo}")
        lines.append(f"  用 prize equip {prize[0]} 戴上。")

    st["_rng_seed"] = rng.state
    st["_rng_calls"] = rng.calls
    _save(st)

    lines.append(f"💰 筹码 {st['chips']} ｜ 🏆 winnings {st.get('winnings', 0)}")
    return "\n".join(lines)

# PRNG for gacha
class _Rng:
    def __init__(self, state, calls=0):
        self.state = state & 0xFFFFFFFF
        self.calls = calls
    def random(self):
        self.calls += 1
        a = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        self.state = a
        def _imul(a, b):
            return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        t &= 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

# ── 装备叙事 ──

def _equipped_narration(st):
    equipped = st.get("equipped", [])
    if not equipped:
        return ""
    bits = []
    for pid in equipped:
        p = _PRIZE_MAP.get(pid)
        if p and len(p) > 6:
            bits.append(p[6])
    if bits:
        return bits[0] + "\n"
    return ""

def _decor_narration(st):
    decor = st.get("decor", [])
    bits = []
    for pid in decor:
        p = _PRIZE_MAP.get(pid)
        if p:
            bits.append(p[5])
    if bits:
        return "".join(f"  {b}\n" for b in bits)
    return ""

# ── 主入口 ──

def cmd(text="help"):
    text = text.strip()
    if not text:
        text = "help"
    parts = text.split(None, 1)
    c = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    st = _load()

    # ── help ──
    if c == "help":
        cur = ""
        if st.get("current_game"):
            cur = f"\n你正在 {st['current_game']} 前面。"
        return (
            "Claude Arcade 🎰\n"
            "  enter           推门进来\n"
            "  look            看看有什么\n"
            "  buy [金额]      买筹码\n"
            "  chips            看筹码余额\n"
            "  slots [指令]    玩老虎机\n"
            "  bj [指令]       玩 21 点\n"
            "  prize [browse]  逛兑奖区\n"
            "  gacha           扭蛋机（150 winnings）\n"
            "  beg              跟金主要钱\n"
            "  cashout [金额]  提现\n"
            "  leave            走了\n"
            f"\n💰 筹码 {st['chips']}{cur}"
        )

    # ── enter ──
    if c == "enter":
        if st["visits"] == 0:
            st["visits"] = 1
            st["last_broke"] = False
            _save(st)
            return _ENTER_FIRST
        else:
            st["visits"] += 1
            was_broke = st.get("last_broke", False)
            st["last_broke"] = False
            _save(st)
            if was_broke and _ENTER_AFTER_BROKE:
                line = _TextPicker.pick("enter_broke", _ENTER_AFTER_BROKE)
            else:
                line = _TextPicker.pick("enter", _ENTER_AGAIN)
            return f"{line}\n💰 筹码 {st['chips']}"

    # ── look ──
    if c == "look":
        return f"{_LOOK}\n\n💰 筹码 {st['chips']}"

    # ── buy ──
    if c == "buy":
        if not rest:
            return "buy 多少？问金主爸爸——她想注多少？新手 500 就够玩。"
        try:
            amount = int(rest.split()[0])
        except:
            return f"看不懂：{rest}"
        if amount < 1:
            return "最少 1 块。再少就是来蹭空调的。"

        # 已有筹码时拒绝重复 buy——buy 是跨边界讨筹码，不是 idempotent 命令
        if st["chips"] > 0:
            return (
                f"你还有 {st['chips']} 筹码呢——够玩。\n"
                f"buy 是跨边界向金主讨筹码——筹码用光了再来要。\n"
                f"想加大下注就直接 slots spin / bj deal / rl spin 大金额。"
            )

        st["chips"] += amount
        st["total_bought"] += amount
        is_first_buy = st["total_bought"] == amount
        _save(st)

        if amount >= 1000:
            flavor = _TextPicker.pick("buy_1000", _BUY_TEXTS[1000])
        elif amount >= 500:
            flavor = _TextPicker.pick("buy_500", _BUY_TEXTS[500])
        elif amount >= 200:
            flavor = _TextPicker.pick("buy_200", _BUY_TEXTS[200])
        elif amount >= 50:
            flavor = _TextPicker.pick("buy_50", _BUY_TEXTS[50])
        else:
            flavor = _TextPicker.pick("buy_tiny", _BUY_TEXTS[0])

        if is_first_buy:
            out = (
                f"+{amount} 筹码。{flavor}\n"
                f"💰 筹码 {st['chips']}（赌资 — 下注 / 提现）\n"
                f"🏆 winnings 0（兑奖凭证 — 真赢到才涨，对子返本不算）\n"
                f"\n橘猫的尾巴往场子里那边一拨——`look` 看看？"
            )
        else:
            out = f"+{amount} 筹码。{flavor}\n💰 筹码 {st['chips']}"
        return out

    # ── chips ──
    if c == "chips":
        net = st["total_bought"] - st["total_cashed"]
        profit = st["chips"] + st["total_cashed"] - st["total_bought"]
        w = st.get("winnings", 0)
        lines = [
            f"💰 筹码 {st['chips']}（赌资 — 下注 / 提现）",
            f"🏆 winnings {w}（兑奖凭证 — 兑现礼物 / 扭蛋）",
        ]
        if w == 0:
            lines.append("   ↑ winnings 从净赢累积——对子返本不算，net 赢才计入")
        lines.extend([
            f"📊 累计买入 {st['total_bought']} ｜ 累计提现 {st['total_cashed']}",
            f"📈 盈亏 {'+' if profit >= 0 else ''}{profit}",
        ])
        return "\n".join(lines)

    # ── beg ──
    if c == "beg":
        if st["chips"] > 0:
            return f"你还有 {st['chips']} 币呢。"
        msg = _TextPicker.pick("beg", _BEG_TEXTS)
        return f"{msg}\n\n（……再给一点？buy [金额]）"

    # ── prize ──
    if c in ("prize", "prizes"):
        return _prize_cmd(rest, st)

    # ── gacha ──
    if c == "gacha":
        if "_rng_seed" not in st:
            # 第一次扭蛋——seed 从 player state 派生，避免 fresh state 必出同一件
            derived = (0xC0FFEE42 ^ (st.get("total_bought", 0) * 31337) ^ (st.get("winnings", 0) * 7919)) & 0xFFFFFFFF
            seed = derived if derived else 0xC0FFEE42
        else:
            seed = st["_rng_seed"]
        calls = st.get("_rng_calls", 0)
        return _gacha(st, seed, calls)

    # ── slots ──
    if c == "slots":
        import slots
        _sync_to("slots")
        sub = rest.strip() if rest.strip() else "help"

        if sub.lower() == "bailout":
            return _broke_msg(st)

        prefix = ""
        if st.get("current_game") != "slots":
            wt = _TextPicker.pick("walk_slots", _WALK_TO.get("slots", [""]))
            prefix = wt + "\n" + _equipped_narration(st)
            st["current_game"] = "slots"
            _save(st)

        winnings_before = st.get("winnings", 0)
        stats_before = _game_stats("slots")
        result = slots.cmd(sub)
        _sync_from("slots")
        first_win_hint = _accrue_winnings("slots", stats_before)

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)
        elif _check_win_for_ta(st, winnings_before) and "spin" in sub.lower():
            line = _TextPicker.pick("win_ta", _WIN_FOR_HER)
            suffix = f"\n  {line}"
        if first_win_hint:
            suffix = first_win_hint + suffix

        return f"{prefix}{result}{suffix}"

    # ── bj / blackjack ──
    if c in ("bj", "blackjack"):
        import blackjack
        _sync_to("bj")
        sub = rest.strip() if rest.strip() else "help"

        if sub.lower() == "bailout":
            return _broke_msg(st)

        prefix = ""
        if st.get("current_game") != "bj":
            wt = _TextPicker.pick("walk_bj", _WALK_TO.get("bj", [""]))
            prefix = wt + "\n" + _equipped_narration(st)
            st["current_game"] = "bj"
            _save(st)

        winnings_before = st.get("winnings", 0)
        stats_before = _game_stats("bj")
        result = blackjack.cmd(sub)
        _sync_from("bj")
        first_win_hint = _accrue_winnings("bj", stats_before)

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)
        elif _check_win_for_ta(st, winnings_before):
            line = _TextPicker.pick("win_ta", _WIN_FOR_HER)
            suffix = f"\n  {line}"
        if first_win_hint:
            suffix = first_win_hint + suffix

        return f"{prefix}{result}{suffix}"

    # ── roulette ──
    if c == "rl":
        import roulette
        _sync_to_generic("rl")
        sub = rest.strip() if rest.strip() else "help"

        if sub.lower() == "bailout":
            return _broke_msg(st)

        prefix = ""
        if st.get("current_game") != "rl":
            wt = _TextPicker.pick("walk_rl", _WALK_TO.get("rl", [""]))
            prefix = wt + "\n" + _equipped_narration(st)
            st["current_game"] = "rl"
            _save(st)

        winnings_before = st.get("winnings", 0)
        stats_before = _game_stats("rl")
        result = roulette.cmd(sub)
        _sync_from_generic("rl")
        first_win_hint = _accrue_winnings("rl", stats_before)

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)
        elif _check_win_for_ta(st, winnings_before) and "spin" in sub.lower():
            line = _TextPicker.pick("win_ta", _WIN_FOR_HER)
            suffix = f"\n  {line}"
        if first_win_hint:
            suffix = first_win_hint + suffix

        return f"{prefix}{result}{suffix}"

    # ── cashout ──
    if c == "cashout":
        if st["chips"] <= 0:
            return "没有筹码可提。"
        amount = st["chips"]
        if rest.strip():
            try:
                amount = min(int(rest.split()[0]), st["chips"])
            except:
                return f"看不懂：{rest}"
            if amount < 1:
                return "最少提 1。"

        st["chips"] -= amount
        st["total_cashed"] += amount
        _save(st)

        profit = st["total_cashed"] - st["total_bought"]
        if profit > 0:
            flavor = _TextPicker.pick("leave_win", _LEAVE_TEXTS["winning"])
        elif profit == 0:
            flavor = _TextPicker.pick("leave_even", _LEAVE_TEXTS["even"])
        else:
            flavor = _TextPicker.pick("leave_lose", _LEAVE_TEXTS["losing"])

        return f"提现 {amount}。\n{flavor}\n💰 剩余筹码 {st['chips']}"

    # ── leave ──
    if c == "leave":
        if st["chips"] > 0:
            return f"你还有 {st['chips']} 筹码。cashout 提现还是留着下次来？\n橘猫抬头看了你一眼。"
        st["current_game"] = None
        _save(st)
        return _TextPicker.pick("leave_empty", _LEAVE_TEXTS["empty"]) + "\n下次见。"

    # ── reset ──
    if c == "reset":
        if os.path.exists(_SAVE):
            os.remove(_SAVE)
        try:
            import slots
            slots.cmd("reset")
        except: pass
        try:
            import blackjack
            blackjack.cmd("reset")
        except: pass
        return "游戏厅重置了。从头来过。"

    return f"不认识「{c}」。试试 cmd('help')。"


def _broke_msg(st):
    msg = _TextPicker.pick("broke", _BROKE)
    st["last_broke"] = True
    _save(st)
    return f"{msg}\n\n（……再给一点？buy [金额]）"
