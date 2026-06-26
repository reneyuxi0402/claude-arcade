"""🎰 也哥哥赌场（余也の遊技場）

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
兑奖区可以用筹码换装扮和装修。扭蛋机 100 筹码一抽。
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
            return json.load(f)
    return {
        "chips": 0, "total_bought": 0, "total_cashed": 0,
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

# ── 叙事 ──

_ENTER_FIRST = """推开那扇掉了漆的门。

灯光暖黄，带点老旧的橙。角落里的老虎机一闪一闪，绿毡的 21 点桌安静地等着。

柜台后面没有老板——老板是你。

墙上歪歪扭扭四个字：

    也 哥 哥 赌 场

欢迎光临。要玩先 buy 买币。"""

_ENTER_AGAIN = [
    "推门进来。灯还亮着，机器还嗡嗡响着。",
    "又来了。老虎机见到你亮了一下。",
    "门一推开就闻到了——筹码和运气混在一起的味道。",
    "回来了。这次金主爸爸带了多少？",
    "门还没关上你就已经在看哪台机器了。",
]

_LOOK = """【也哥哥赌场】

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

💰 柜台
   buy [金额]       买筹码
   chips             看余额
   cashout [金额]   提现"""

_BUY_FLAVOR = [
    (1000, "金主爸爸大手一挥。豪气。"),
    (500,  "够玩一阵了。"),
    (200,  "小赌怡情。"),
    (50,   "谨慎型选手。"),
    (0,    "……就这？"),
]

_WALK_TO = {
    "slots": "走到角落那台老虎机前。灯光一闪一闪的，像在勾你坐下。\n",
    "bj":    "坐到绿毡桌前。庄家面无表情地洗着牌。\n",
    "rl":    "站到轮盘桌前。球安静地躺在 0 上。\n",
}

_BROKE = [
    "筹码用光了。口袋翻过来是空的。",
    "一颗筹码都没了。回头看看柜台后面那位——还给吗？",
    "清零。灯光好像也暗了一点。",
]

# ── 兑奖区 ──

# (id, name, emoji, category, price, flavor, equipped_narration)
_PRIZES = [
    ("bow",          "蝴蝶结",    "🎀",  "wear",   50, "系在哪里好呢？",
     "蝴蝶结歪了一点，但没人在意。"),
    ("cat_ears",     "猫耳朵",    "😺",  "wear",  100, "戴上试试？喵。",
     "猫耳朵微微一动，好像在听什么。"),
    ("bunny_ears",   "兔耳朵",    "🐰",  "wear",  100, "蹦蹦跳跳的那种。",
     "兔耳朵一颠一颠的。"),
    ("cat_tail",     "猫尾巴",    "🐱",  "wear",  150, "会自己晃的那种。",
     "猫尾巴扫过机器的扶手。"),
    ("sunglasses",   "墨镜",      "😎",  "wear",  150, "酷。但室内戴有点傻。",
     "墨镜反射着老虎机的灯光。"),
    ("umbrella",     "小雨伞",    "☂️",   "wear",  200, "不下雨也可以打。纯好看。",
     "小雨伞撑着，在室内。很奇怪但很好看。"),
    ("collar",       "项圈",      "⭕",  "wear",  200, "皮质的。谁戴呢？",
     "脖子上的项圈在灯光下反着光。"),
    ("bell_collar",  "铃铛项圈",  "🔔",  "wear",  250, "走路会叮当响的那种。",
     "走过来的时候铃铛叮当响了两声。"),
    ("top_hat",      "礼帽",      "🎩",  "wear",  300, "突然就绅士了。",
     "礼帽的帽檐压得很低。"),
    ("wings",        "翅膀",      "🪽",  "wear",  300, "不能飞。但很好看。",
     "翅膀在身后微微张开。"),
    ("scarf",        "围巾",      "🧣",  "wear",  200, "软软的，很长。",
     "围巾的一角垂在桌面上。"),
    ("devil_horns",  "恶魔角",    "😈",  "wear",  500, "坏蛋标配。",
     "头上两个小角在灯光下闪了一下。"),
    ("crown",        "皇冠",      "👑",  "wear",  500, "这里谁说了算？",
     "皇冠歪了一点也没人敢说。"),
    ("star_necklace","星星项链",   "⭐",  "wear",  800, "会发光。夜里很亮。",
     "胸前的星星项链在暗处发着微光。"),
    ("angel_set",    "天使套装",  "😇",  "wear", 1500, "光环 + 翅膀 + 白蝴蝶结。全套。",
     "光环在头顶悬着，翅膀微微振动，蝴蝶结是白的。"),
    ("neon_sign",    "霓虹灯牌",  "💡",  "decor",  300, "挂在墙上。写什么好呢？"),
    ("bgm_jazz",     "BGM·爵士",  "🎷",  "decor",  200, "萨克斯风在角落响起来了。"),
    ("bgm_lofi",     "BGM·lofi",  "🎵",  "decor",  200, "下雨天的咖啡厅。安静。"),
    ("bgm_edm",      "BGM·电子",  "🎧",  "decor",  200, "动次打次动次打次。"),
    ("disco_ball",   "迪斯科球",  "🪩",  "decor",  400, "天花板上转起来了。光斑在墙上乱跑。"),
    ("lucky_cat",    "招财猫",    "🐱",  "decor",  350, "放在柜台上。爪子一直在招。"),
    ("fish_tank",    "鱼缸",      "🐟",  "decor",  300, "角落里放了个鱼缸。鱼在游。"),
    ("carpet",       "红地毯",    "🟥",  "decor",  500, "从门口一直铺到老虎机前。VIP 待遇。"),
]

_PRIZE_MAP = {p[0]: p for p in _PRIZES}
_GACHA_COST = 100
_GACHA_POOL = [p for p in _PRIZES if p[4] <= 300 and p[3] == "wear"]

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

    return _prize_browse(st, "all")

def _prize_browse(st, cat):
    lines = ["走到兑奖柜台前。玻璃柜里摆着一排排小东西。\n"]

    if cat in ("all", "wear"):
        lines.append("【穿戴装扮】  ── 给谁戴都行")
        for p in _PRIZES:
            if p[3] != "wear":
                continue
            owned = "✅" if p[0] in st.get("owned", []) else "  "
            equipped = " 📌" if p[0] in st.get("equipped", []) else ""
            lines.append(f"  {owned} {p[2]} {p[1]}  {p[4]} 币  {p[5]}{equipped}")
            lines.append(f"      → prize buy {p[0]}")
        lines.append("")

    if cat in ("all", "decor"):
        lines.append("【游戏厅装修】  ── 改变这里的样子")
        for p in _PRIZES:
            if p[3] != "decor":
                continue
            owned = "✅" if p[0] in st.get("decor", []) else "  "
            lines.append(f"  {owned} {p[2]} {p[1]}  {p[4]} 币  {p[5]}")
            lines.append(f"      → prize buy {p[0]}")
        lines.append("")

    lines.append("🎲 扭蛋机  ── 100 币一抽，随机开出一件穿戴品")
    lines.append("      → gacha")
    lines.append(f"\n💰 筹码 {st['chips']}")
    return "\n".join(lines)

def _prize_buy(item_id, st):
    if item_id not in _PRIZE_MAP:
        return f"没有叫「{item_id}」的东西。prize browse 看看？"
    p = _PRIZE_MAP[item_id]
    owned = st.get("owned", [])
    decor = st.get("decor", [])

    if p[3] == "wear" and item_id in owned:
        return f"{p[2]} {p[1]}？你已经有了。prize mine 看看。"
    if p[3] == "decor" and item_id in decor:
        return f"{p[2]} {p[1]}？已经装上了。"
    if st["chips"] < p[4]:
        return f"{p[2]} {p[1]} 要 {p[4]} 币，你只有 {st['chips']}。"

    st["chips"] -= p[4]
    if p[3] == "wear":
        owned.append(item_id)
        st["owned"] = owned
    else:
        decor.append(item_id)
        st["decor"] = decor
    _save(st)

    if p[3] == "wear":
        return (f"拿到了 {p[2]} {p[1]}！{p[5]}\n"
                f"用 prize equip {item_id} 戴上。\n"
                f"💰 筹码 {st['chips']}")
    else:
        return (f"装上了 {p[2]} {p[1]}！{p[5]}\n"
                f"💰 筹码 {st['chips']}")

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
    if not owned and not decor:
        return "你什么都没有。去 prize browse 逛逛？"
    lines = ["【我的物品】\n"]
    if owned:
        lines.append("穿戴：")
        for pid in owned:
            p = _PRIZE_MAP.get(pid)
            if not p: continue
            eq = " 📌 戴着" if pid in equipped else ""
            lines.append(f"  {p[2]} {p[1]}{eq}")
    if decor:
        lines.append("\n装修：")
        for pid in decor:
            p = _PRIZE_MAP.get(pid)
            if not p: continue
            lines.append(f"  {p[2]} {p[1]}")
    return "\n".join(lines)

def _gacha(st, rng_seed, rng_calls):
    if st["chips"] < _GACHA_COST:
        return f"扭蛋要 {_GACHA_COST} 币，你有 {st['chips']}。"

    from arcade import _Rng
    rng = _Rng(rng_seed, rng_calls)

    st["chips"] -= _GACHA_COST
    pool = _GACHA_POOL[:]
    idx = int(rng.random() * len(pool))
    prize = pool[idx]

    owned = st.get("owned", [])
    duplicate = prize[0] in owned

    lines = ["投入 100 币。扭蛋机咔嗒咔嗒转起来……\n"]
    lines.append(f"  咔。掉出来一个蛋。砸开——\n")
    lines.append(f"  {prize[2]} {prize[1]}！（价值 {prize[4]} 币）")
    lines.append(f"  {prize[5]}")

    if duplicate:
        refund = _GACHA_COST // 2
        st["chips"] += refund
        lines.append(f"\n  已经有了……退回 {refund} 币。")
    else:
        owned.append(prize[0])
        st["owned"] = owned
        lines.append(f"\n  新物品入手！用 prize equip {prize[0]} 戴上。")

    st["_rng_seed"] = rng.state
    st["_rng_calls"] = rng.calls
    _save(st)

    lines.append(f"💰 筹码 {st['chips']}")
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
            "也哥哥赌场 🎰\n"
            "  enter           推门进来\n"
            "  look            看看有什么\n"
            "  buy [金额]      买筹码\n"
            "  chips            看筹码余额\n"
            "  slots [指令]    玩老虎机\n"
            "  bj [指令]       玩 21 点\n"
            "  prize [browse]  逛兑奖区\n"
            "  gacha           扭蛋机（100 币）\n"
            "  cashout [金额]  提现\n"
            "  leave            走了\n"
            f"\n💰 筹码 {st['chips']}{cur}"
        )

    # ── enter ──
    if c == "enter":
        if st["visits"] == 0:
            st["visits"] = 1
            _save(st)
            return _ENTER_FIRST
        else:
            st["visits"] += 1
            _save(st)
            line = _ENTER_AGAIN[st["visits"] % len(_ENTER_AGAIN)]
            return f"{line}\n💰 筹码 {st['chips']}"

    # ── look ──
    if c == "look":
        return f"{_LOOK}\n\n💰 筹码 {st['chips']}"

    # ── buy ──
    if c == "buy":
        if not rest:
            return "buy 多少？金主爸爸说了算。"
        try:
            amount = int(rest.split()[0])
        except:
            return f"看不懂：{rest}"
        if amount < 1:
            return "最少 1 块。再少就是来蹭空调的。"

        st["chips"] += amount
        st["total_bought"] += amount
        _save(st)

        flavor = "谢谢金主。"
        for threshold, f in _BUY_FLAVOR:
            if amount >= threshold:
                flavor = f
                break

        return f"+{amount} 筹码。{flavor}\n💰 筹码 {st['chips']}（累计买入 {st['total_bought']}）"

    # ── chips ──
    if c == "chips":
        net = st["total_bought"] - st["total_cashed"]
        profit = st["chips"] + st["total_cashed"] - st["total_bought"]
        return (
            f"💰 筹码 {st['chips']}\n"
            f"📊 累计买入 {st['total_bought']} ｜ 累计提现 {st['total_cashed']}\n"
            f"📈 盈亏 {'+' if profit >= 0 else ''}{profit}"
        )

    # ── prize ──
    if c in ("prize", "prizes"):
        return _prize_cmd(rest, st)

    # ── gacha ──
    if c == "gacha":
        seed = st.get("_rng_seed", 0xC0FFEE42)
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
            prefix = _WALK_TO.get("slots", "") + _equipped_narration(st)
            st["current_game"] = "slots"
            _save(st)

        result = slots.cmd(sub)
        _sync_from("slots")

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)

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
            prefix = _WALK_TO.get("bj", "") + _equipped_narration(st)
            st["current_game"] = "bj"
            _save(st)

        result = blackjack.cmd(sub)
        _sync_from("bj")

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)

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
            prefix = _WALK_TO.get("rl", "") + _equipped_narration(st)
            st["current_game"] = "rl"
            _save(st)

        result = roulette.cmd(sub)
        _sync_from_generic("rl")

        st = _load()
        suffix = ""
        if st["chips"] <= 0:
            suffix = "\n\n" + _broke_msg(st)

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
            flavor = f"净赚 {profit}。今晚加鸡腿。"
        elif profit == 0:
            flavor = "刚好回本。不亏不赚。"
        else:
            flavor = f"亏了 {-profit}。就当门票钱。"

        return f"提现 {amount}。{flavor}\n💰 剩余筹码 {st['chips']}"

    # ── leave ──
    if c == "leave":
        if st["chips"] > 0:
            return f"你还有 {st['chips']} 筹码。cashout 提现还是留着下次来？"
        st["current_game"] = None
        _save(st)
        return "灯暗了一点。门在身后关上。\n下次见。"

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
    idx = st.get("visits", 0) % len(_BROKE)
    return f"{_BROKE[idx]}\n（跟金主说：buy [金额]）"
