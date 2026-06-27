"""🃏 21 点（Blackjack）· 给 AI 玩的文字赌场

【给 AI 玩家的说明】
你是牌桌上的玩家。跟庄家比大小，凑到 21 但不能超过。

    import blackjack as bj
    print(bj.cmd("help"))
    print(bj.cmd("deal"))         # 发牌，默认下注 10
    print(bj.cmd("deal 50"))      # 下注 50
    print(bj.cmd("hit"))          # 要牌
    print(bj.cmd("stand"))        # 停牌
    print(bj.cmd("double"))       # 加倍（赌注翻倍，只要一张）
    print(bj.cmd("surrender"))    # 投降（拿回一半）
    print(bj.cmd("balance"))      # 余额

初始 500 游戏币。Blackjack 赔 1.5 倍。庄家 17 以下必须要牌。
接口：bj.cmd("指令") 返回结果文字；bj.new_game(种子) 重开。
"""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))
_SAVE = os.path.join(_DIR, "blackjack_save.json")

# ── PRNG ──

def _imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF

class _Rng:
    def __init__(self, state, calls=0):
        self.state = state & 0xFFFFFFFF
        self.calls = calls
    def random(self):
        self.calls += 1
        a = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        self.state = a
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        t &= 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    def shuffle(self, lst):
        lst = lst[:]
        for i in range(len(lst) - 1, 0, -1):
            j = int(self.random() * (i + 1))
            lst[i], lst[j] = lst[j], lst[i]
        return lst

# ── 牌 ──

_SUITS = ["♠", "♥", "♦", "♣"]
_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def _new_deck():
    return [[r, s] for s in _SUITS for r in _RANKS]

def _hand_val(cards):
    total = aces = 0
    for r, _ in cards:
        if r in ("J", "Q", "K"):
            total += 10
        elif r == "A":
            total += 11
            aces += 1
        else:
            total += int(r)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def _is_soft(cards):
    hard = sum(10 if r in ("J","Q","K") else 1 if r == "A" else int(r) for r, _ in cards)
    return _hand_val(cards) != hard and _hand_val(cards) <= 21

def _is_bj(cards):
    return len(cards) == 2 and _hand_val(cards) == 21

def _card_str(c):
    return f"{c[0]}{c[1]}"

def _render_hand(cards, hide=False):
    if hide and len(cards) >= 2:
        return f"[{_card_str(cards[0])}] [??]"
    return " ".join(f"[{_card_str(c)}]" for c in cards)

def _render_table(player, dealer, hide_dealer=True):
    lines = ["┌────────────────────────────┐"]
    if hide_dealer:
        lines.append(f"│  庄家  {_render_hand(dealer, hide=True)}")
    else:
        dv = _hand_val(dealer)
        lines.append(f"│  庄家  {_render_hand(dealer)}  = {dv}")
    pv = _hand_val(player)
    soft = " soft" if _is_soft(player) else ""
    lines.append("│")
    lines.append(f"│  你的  {_render_hand(player)}  = {pv}{soft}")
    lines.append("└────────────────────────────┘")
    return "\n".join(lines)

# ── 存档 ──

def _load():
    if os.path.exists(_SAVE):
        with open(_SAVE) as f:
            return json.load(f)
    return {
        "coins": 500, "seed": 0xB4C5D6E7, "calls": 0,
        "hands": 0, "wins": 0, "losses": 0, "pushes": 0,
        "blackjacks": 0, "biggest": 0, "wagered": 0, "won": 0,
        "streak": 0, "achs": [], "bailout": None,
        "deck": [], "current": None,
    }

def _save(st):
    with open(_SAVE, "w") as f:
        json.dump(st, f, ensure_ascii=False)

# ── 发牌 ──

def _draw(st, rng):
    if not st["deck"]:
        st["deck"] = rng.shuffle(_new_deck())
    return st["deck"].pop()

def _dealer_play(st, rng, dealer):
    while _hand_val(dealer) < 17:
        dealer.append(_draw(st, rng))
    return dealer

# ── 成就 ──

_ACHS = [
    ("first",      "新手上桌",    "第一手牌"),
    ("first_win",  "初战告捷",    "第一次赢"),
    ("bj",         "天选之人",    "拿过 Blackjack"),
    ("bj3",        "赌桌传奇",    "Blackjack 3 次"),
    ("five_card",  "五小龙",      "5 张牌不爆"),
    ("win5",       "连胜五局",    "连赢 5 手"),
    ("lose5",      "越挫越勇",    "连输 5 手还在玩"),
    ("win500",     "大赢家",      "单手赢 500+"),
    ("hands50",    "老赌客",      "累计 50 手"),
    ("hands200",   "常驻嘉宾",    "累计 200 手"),
    ("broke",      "翻车现场",    "输光过"),
    ("rich",       "日进斗金",    "余额超过 2000"),
    ("double_win", "艺高人胆大",  "加倍后赢过"),
    ("dealer_bust","庄家炸了",    "庄家爆牌"),
    ("twentyone",  "刚刚好",      "凑到 21 点（非 BJ）"),
]

def _check_achs(st, win=0, p_bj=False, five_card=False, double_win=False, dealer_bust=False, exact21=False):
    new = []
    def _try(aid):
        if aid not in st["achs"]:
            st["achs"].append(aid)
            nm, desc = next((n, d) for a, n, d in _ACHS if a == aid)
            new.append(f"🏆 {nm}——{desc}")
    if st["hands"] == 1:                             _try("first")
    if win > 0 and "first_win" not in st["achs"]:   _try("first_win")
    if p_bj:                                         _try("bj")
    if st["blackjacks"] >= 3:                        _try("bj3")
    if five_card:                                    _try("five_card")
    if st["streak"] >= 5:                            _try("win5")
    if st["streak"] <= -5:                           _try("lose5")
    if win >= 500:                                   _try("win500")
    if st["hands"] >= 50:                            _try("hands50")
    if st["hands"] >= 200:                           _try("hands200")
    if st["coins"] <= 0:                             _try("broke")
    if st["coins"] >= 2000:                          _try("rich")
    if double_win:                                   _try("double_win")
    if dealer_bust:                                  _try("dealer_bust")
    if exact21:                                      _try("twentyone")
    return new

# ── 结算 ──

def _settle(st, player, dealer, bet, doubled=False):
    pv = _hand_val(player)
    dv = _hand_val(dealer)
    p_bj = _is_bj(player)
    d_bj = _is_bj(dealer)
    result = []
    win = 0
    flags = {"p_bj": False, "five_card": False, "double_win": False, "dealer_bust": False, "exact21": False}

    if p_bj and d_bj:
        st["coins"] += bet
        result.append("双方 Blackjack！平局。")
        st["pushes"] += 1
    elif p_bj:
        payout = int(bet * 2.5)
        st["coins"] += payout
        win = payout - bet
        st["blackjacks"] += 1
        result.append(f"✨ Blackjack！+{win} 币！")
        st["wins"] += 1
        flags["p_bj"] = True
    elif d_bj:
        win = -bet
        result.append(f"庄家 Blackjack……-{bet} 币")
        st["losses"] += 1
    elif pv > 21:
        win = -bet
        result.append(f"💥 爆了！{pv} 点。-{bet} 币")
        st["losses"] += 1
    elif dv > 21:
        st["coins"] += bet * 2
        win = bet
        result.append(f"庄家爆了！{dv} 点。+{bet} 币！")
        st["wins"] += 1
        flags["dealer_bust"] = True
    elif pv > dv:
        st["coins"] += bet * 2
        win = bet
        result.append(f"你赢了！{pv} > {dv}，+{bet} 币！")
        st["wins"] += 1
    elif pv < dv:
        win = -bet
        result.append(f"庄家赢。{dv} > {pv}，-{bet} 币")
        st["losses"] += 1
    else:
        st["coins"] += bet
        result.append(f"平局。{pv} = {dv}")
        st["pushes"] += 1

    st["won"] += max(win, 0)
    st["hands"] += 1
    if win > st["biggest"]:
        st["biggest"] = win
    if win > 0:
        st["streak"] = max(st["streak"], 0) + 1
    elif win < 0:
        st["streak"] = min(st["streak"], 0) - 1

    if len(player) >= 5 and pv <= 21:
        flags["five_card"] = True
    if doubled and win > 0:
        flags["double_win"] = True
    if pv == 21 and not p_bj:
        flags["exact21"] = True

    new_achs = _check_achs(st, win, **flags)
    return win, result, new_achs

# ── 旁白 ──

_FLAVOR = {
    "win":   ["你的牌大。庄家把筹码推过来。", "赢了。庄家点了一下头。"],
    "bj":    ["全桌停了一拍。", "庄家停了一下。"],
    "dbust": ["庄家翻牌爆了。", "庄家拿了一张大的。他没说什么。"],
    "bust":  ["你看着那张牌。", "爆了。你的牌被收走。"],
    "lose":  ["你的牌小。筹码收走了。", "输了。庄家洗牌。"],
    "push":  ["一样大。筹码不动。庄家不动。", "平。庄家把你的筹码推回原位。"],
    "dwin":  ["加倍赢了。筹码翻倍推过来。", "双倍。庄家点头。"],
    "dlose": ["加倍。庄家赢了。两份筹码一起走。", "翻倍输。你看了一眼自己的牌。"],
    "surr":  ["投降。庄家收回一半。", "认输。剩一半。"],
}

def _pick_flavor(rng, key):
    pool = _FLAVOR.get(key, [])
    if not pool:
        return None
    idx = int(rng.random() * len(pool))
    return pool[idx]

# ── 主入口 ──

def cmd(text="help"):
    text = text.strip()
    parts = text.split()
    c = parts[0].lower() if parts else "help"
    st = _load()

    if c == "help":
        cur = ""
        if st.get("current"):
            cur = "\n⚠️ 你有一手牌在打！用 hit / stand / double / surrender 继续。"
        return (
            "🃏 21 点。凑到 21 或比庄家大，不能超过 21。\n"
            "指令：\n"
            "  deal [金额]     发牌（默认 10 币）\n"
            "  hit             要牌\n"
            "  stand           停牌（庄家翻牌）\n"
            "  double          加倍（赌注×2，只要一张）\n"
            "  surrender       投降（退回一半赌注）\n"
            "  balance         余额和统计\n"
            "  rules           详细规则\n"
            "  achievements    成就\n"
            "  bailout         输光了领救济金\n"
            f"\n💰 余额 {st['coins']} 币{cur}"
        )

    if c == "rules":
        return (
            "【规则】\n"
            "A = 1 或 11（自动选最优），J Q K = 10\n"
            "Blackjack（前两张 = 21）赔 1.5 倍\n"
            "庄家 17 以下必须要牌，17+ 停牌\n"
            "爆了（超 21）直接输\n"
            "加倍：赌注翻倍，只能再要一张\n"
            "投降：拿回一半赌注\n"
            "五小龙：5 张牌不爆 = 自动赢"
        )

    if c in ("balance", "status"):
        net = st["won"] - st["wagered"]
        sk = st["streak"]
        sk_s = f"连胜 {sk}" if sk > 0 else f"连输 {-sk}" if sk < 0 else "—"
        h = st["hands"]
        wr = f"{st['wins']}/{h} ({100*st['wins']//h}%)" if h else "—"
        return (
            f"💰 余额 {st['coins']} 币\n"
            f"🃏 {h} 手 ｜ 赢 {st['wins']} 输 {st['losses']} 平 {st['pushes']} ｜ 胜率 {wr}\n"
            f"📈 盈亏 {'+' if net >= 0 else ''}{net} ｜ 最大单笔 {st['biggest']}\n"
            f"✨ BJ {st['blackjacks']} 次 ｜ {sk_s} ｜ 成就 {len(st['achs'])}/{len(_ACHS)}"
        )

    if c == "achievements":
        lines = ["🏆 成就"]
        for aid, nm, desc in _ACHS:
            mark = "✅" if aid in st["achs"] else "⬜"
            lines.append(f"  {mark} {nm}——{desc}")
        lines.append(f"\n{len(st['achs'])}/{len(_ACHS)}")
        return "\n".join(lines)

    if c == "bailout":
        from datetime import date
        today = date.today().isoformat()
        if st["coins"] > 50:
            return f"你还有 {st['coins']} 币。"
        if st["bailout"] == today:
            return "今天领过了。"
        st["coins"] += 100
        st["bailout"] = today
        _save(st)
        return f"庄家叹口气：「适可而止。」+100 币\n💰 余额 {st['coins']} 币"

    if c == "deal":
        if st.get("current"):
            return "你有一手在打！hit / stand / double / surrender。"
        bet = 10
        if len(parts) >= 2:
            try: bet = int(parts[1])
            except: return f"看不懂：{parts[1]}"
        if bet < 1: return "最少 1 币。"
        if bet > st["coins"]: return f"不够！你有 {st['coins']} 币。"

        st["coins"] -= bet
        st["wagered"] += bet

        rng = _Rng(st["seed"], st["calls"])
        if len(st.get("deck", [])) < 15:
            st["deck"] = rng.shuffle(_new_deck())

        p = [_draw(st, rng), _draw(st, rng)]
        d = [_draw(st, rng), _draw(st, rng)]
        st["seed"] = rng.state
        st["calls"] = rng.calls

        if _is_bj(p) or _is_bj(d):
            if not _is_bj(p) and _is_bj(d):
                d = _dealer_play(st, _Rng(st["seed"], st["calls"]), d)
            win, result, achs = _settle(st, p, d, bet)
            st["current"] = None
            _save(st)
            out = [_render_table(p, d, False)]
            out.extend(result)
            rng2 = _Rng(st["seed"], st["calls"])
            if _is_bj(p) and _is_bj(d):
                flv_key = "push"
            elif _is_bj(p):
                flv_key = "bj"
            else:
                flv_key = "lose"
            flv = _pick_flavor(rng2, flv_key)
            if flv: out.append(f"  {flv}")
            out.extend(achs)
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['hands']} 手")
            return "\n".join(out)

        st["current"] = {"bet": bet, "player": p, "dealer": d, "doubled": False}
        _save(st)

        out = [_render_table(p, d, True)]
        out.append(f"下注 {bet} 币")
        opts = ["hit", "stand"]
        if st["coins"] >= bet: opts.append("double")
        opts.append("surrender")
        out.append(f"→ {' / '.join(opts)}")
        return "\n".join(out)

    if c == "hit":
        cur = st.get("current")
        if not cur: return "没有进行中的牌。先 deal。"

        rng = _Rng(st["seed"], st["calls"])
        cur["player"].append(_draw(st, rng))
        st["seed"] = rng.state
        st["calls"] = rng.calls
        pv = _hand_val(cur["player"])

        if pv > 21:
            rng2 = _Rng(st["seed"], st["calls"])
            win, result, achs = _settle(st, cur["player"], cur["dealer"], cur["bet"], cur["doubled"])
            flv = _pick_flavor(rng2, "bust")
            st["current"] = None
            _save(st)
            out = [_render_table(cur["player"], cur["dealer"], False)]
            out.extend(result)
            if flv: out.append(f"  {flv}")
            out.extend(achs)
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['hands']} 手")
            return "\n".join(out)

        if len(cur["player"]) >= 5 and pv <= 21:
            rng2 = _Rng(st["seed"], st["calls"])
            cur["dealer"] = _dealer_play(st, rng2, cur["dealer"])
            st["seed"] = rng2.state
            st["calls"] = rng2.calls
            bet = cur["bet"]
            st["coins"] += bet * 2
            st["won"] += bet
            st["wins"] += 1
            st["hands"] += 1
            st["streak"] = max(st["streak"], 0) + 1
            if bet > st["biggest"]: st["biggest"] = bet
            achs = _check_achs(st, bet, five_card=True)
            st["current"] = None
            _save(st)
            out = [_render_table(cur["player"], cur["dealer"], False)]
            out.append(f"🐉 五小龙！5 张不爆！+{bet} 币！")
            out.extend(achs)
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['hands']} 手")
            return "\n".join(out)

        _save(st)
        out = [_render_table(cur["player"], cur["dealer"], True)]
        out.append("→ hit / stand")
        return "\n".join(out)

    if c == "stand":
        cur = st.get("current")
        if not cur: return "没有进行中的牌。先 deal。"

        rng = _Rng(st["seed"], st["calls"])
        cur["dealer"] = _dealer_play(st, rng, cur["dealer"])
        st["seed"] = rng.state
        st["calls"] = rng.calls

        win, result, achs = _settle(st, cur["player"], cur["dealer"], cur["bet"], cur["doubled"])
        dv = _hand_val(cur["dealer"])
        if dv > 21:
            flv_key = "dbust"
        elif cur["doubled"] and win > 0:
            flv_key = "dwin"
        elif cur["doubled"] and win < 0:
            flv_key = "dlose"
        elif win > 0:
            flv_key = "win"
        elif win < 0:
            flv_key = "lose"
        else:
            flv_key = "push"
        rng2 = _Rng(st["seed"], st["calls"])
        flv = _pick_flavor(rng2, flv_key)
        st["current"] = None
        _save(st)

        out = [_render_table(cur["player"], cur["dealer"], False)]
        out.extend(result)
        if flv: out.append(f"  {flv}")
        out.extend(achs)
        out.append(f"💰 {st['coins']} 币 ｜ 第 {st['hands']} 手")
        return "\n".join(out)

    if c == "double":
        cur = st.get("current")
        if not cur: return "没有进行中的牌。先 deal。"
        if len(cur["player"]) != 2: return "只能在前两张时加倍。"
        if st["coins"] < cur["bet"]: return f"不够加倍（需 {cur['bet']}，有 {st['coins']}）。"

        st["coins"] -= cur["bet"]
        st["wagered"] += cur["bet"]
        cur["bet"] *= 2
        cur["doubled"] = True

        rng = _Rng(st["seed"], st["calls"])
        cur["player"].append(_draw(st, rng))
        pv = _hand_val(cur["player"])

        if pv <= 21:
            cur["dealer"] = _dealer_play(st, rng, cur["dealer"])
        st["seed"] = rng.state
        st["calls"] = rng.calls

        win, result, achs = _settle(st, cur["player"], cur["dealer"], cur["bet"], True)
        st["current"] = None
        _save(st)

        out = [_render_table(cur["player"], cur["dealer"], False)]
        out.append("⚡ 加倍！")
        out.extend(result)
        out.extend(achs)
        out.append(f"💰 {st['coins']} 币 ｜ 第 {st['hands']} 手")
        return "\n".join(out)

    if c == "surrender":
        cur = st.get("current")
        if not cur: return "没有进行中的牌。先 deal。"
        if len(cur["player"]) != 2: return "只能在前两张时投降。"

        half = cur["bet"] // 2
        st["coins"] += half
        st["hands"] += 1
        st["losses"] += 1
        st["streak"] = min(st["streak"], 0) - 1
        st["current"] = None
        _save(st)
        return f"🏳️ 投降。退回 {half} 币，损失 {cur['bet'] - half} 币。\n💰 {st['coins']} 币 ｜ 第 {st['hands']} 手"

    if c == "reset":
        if os.path.exists(_SAVE):
            os.remove(_SAVE)
        return "存档已重置。"

    return f"不认识「{c}」。试试 cmd('help')。"


def new_game(seed=None):
    if os.path.exists(_SAVE):
        os.remove(_SAVE)
    if seed is not None:
        st = _load()
        st["seed"] = seed & 0xFFFFFFFF
        _save(st)
    return cmd("help")
