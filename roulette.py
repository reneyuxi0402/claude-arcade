"""🎡 轮盘赌（Roulette）· 给 AI 玩的文字赌场

【给 AI 玩家的说明】
你是轮盘桌前的赌客。猜球会落在哪里。

    import roulette as rl
    print(rl.cmd("help"))
    print(rl.cmd("spin red 50"))     # 押红 50 币
    print(rl.cmd("spin 17 50"))      # 押 17 号 50 币
    print(rl.cmd("spin odd 50"))     # 押奇数 50 币
    print(rl.cmd("spin red 10 5"))   # 押红 10 币 连转 5 次
    print(rl.cmd("balance"))         # 余额

初始 500 游戏币。单号 35 倍。0 通杀红黑奇偶大小。
接口：rl.cmd("指令") 返回结果文字；rl.new_game(种子) 重开。
"""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))
_SAVE = os.path.join(_DIR, "roulette_save.json")

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
    def rint(self, a, b):
        return a + int(self.random() * (b - a + 1))

# ── 轮盘 ──

_REDS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
_BLACKS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
_WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

def _clr(n):
    if n == 0: return "green"
    return "red" if n in _REDS else "black"

def _sym(n):
    c = _clr(n)
    return "🟢" if c == "green" else "🔴" if c == "red" else "⚫"

def _cn(n):
    c = _clr(n)
    return "绿" if c == "green" else "红" if c == "red" else "黑"

# ── 押注类型 ──

_BETS = {
    "red":   (lambda n: n in _REDS,              1, "红"),
    "black": (lambda n: n in _BLACKS,             1, "黑"),
    "odd":   (lambda n: n != 0 and n % 2 == 1,    1, "奇"),
    "even":  (lambda n: n != 0 and n % 2 == 0,    1, "偶"),
    "low":   (lambda n: 1 <= n <= 18,              1, "小(1-18)"),
    "high":  (lambda n: 19 <= n <= 36,             1, "大(19-36)"),
    "d1":    (lambda n: 1 <= n <= 12,              2, "第一打(1-12)"),
    "d2":    (lambda n: 13 <= n <= 24,             2, "第二打(13-24)"),
    "d3":    (lambda n: 25 <= n <= 36,             2, "第三打(25-36)"),
}

# ── 存档 ──

def _load():
    if os.path.exists(_SAVE):
        with open(_SAVE) as f:
            return json.load(f)
    return {
        "coins": 500, "seed": 0xD1E2F3A4, "calls": 0,
        "spins": 0, "wagered": 0, "won": 0,
        "biggest": 0, "streak": 0,
        "achs": [], "bailout": None,
    }

def _save(st):
    with open(_SAVE, "w") as f:
        json.dump(st, f, ensure_ascii=False)

# ── 成就 ──

_ACHS = [
    ("first",      "初次下注",  "第一次转轮盘"),
    ("first_win",  "新手好运",  "第一次赢"),
    ("straight",   "一击命中",  "押中单个数字（×35）"),
    ("zero",       "零的审判",  "球落在 0 上"),
    ("streak3",    "三连红",    "连赢 3 次"),
    ("lose5",      "头铁",      "连输 5 次还在玩"),
    ("win500",     "豪赌",      "单次赢 500+"),
    ("win1750",    "疯子",      "单次赢 1750+"),
    ("spins50",    "轮盘常客",  "累计 50 次"),
    ("broke",      "一无所有",  "输光过"),
    ("rich",       "轮盘之王",  "余额超过 3000"),
]

def _check_achs(st, win, is_straight=False, is_zero=False):
    new = []
    def _try(aid):
        if aid not in st["achs"]:
            st["achs"].append(aid)
            nm, desc = next((n, d) for a, n, d in _ACHS if a == aid)
            new.append(f"🏆 {nm}——{desc}")
    if st["spins"] == 1:                            _try("first")
    if win > 0 and "first_win" not in st["achs"]:  _try("first_win")
    if is_straight:                                  _try("straight")
    if is_zero:                                      _try("zero")
    if st["streak"] >= 3:                            _try("streak3")
    if st["streak"] <= -5:                           _try("lose5")
    if win >= 500:                                   _try("win500")
    if win >= 1750:                                  _try("win1750")
    if st["spins"] >= 50:                            _try("spins50")
    if st["coins"] <= 0:                             _try("broke")
    if st["coins"] >= 3000:                          _try("rich")
    return new

# ── 近失检测 ──

def _is_neighbor(result, target):
    if result not in _WHEEL or target not in _WHEEL:
        return False
    ri = _WHEEL.index(result)
    ti = _WHEEL.index(target)
    return abs(ri - ti) == 1 or abs(ri - ti) == len(_WHEEL) - 1

# ── 旁白 ──

_RL_TEXTS = {
    "color_win":   ["球停在你押的那边。对了。", "中了。"],
    "color_lose":  ["球停在另一边。", "不是你押的。"],
    "number_win":  ["球停在你押的那个号。整桌停了一秒。", "你的号。35 倍。橘猫站起来了。"],
    "number_lose": ["球滚过你押的格，停在隔壁。", "不是你押的号。"],
    "zero":        ["球停在 0。绿色的。", "0。所有人的筹码都走了。荷官的手很稳。"],
    "near_miss":   ["球在你押的号边上晃了一下，停在隔壁。", "差一格。"],
    "streak_lose": ["又输了。荷官没看你。橘猫的尾巴收了起来。", "球又停在了别的地方。这是第几次了。"],
    "streak_win":  ["又中了。", "连第三次。橘猫坐起来了。"],
}
_rl_text_history = {}

def _rl_pick(key, rng):
    opts = _RL_TEXTS.get(key, [])
    if not opts:
        return None
    recent = _rl_text_history.setdefault(key, [])
    available = [i for i in range(len(opts)) if i not in recent]
    if not available:
        available = list(range(len(opts)))
        recent.clear()
    idx = available[int(rng.random() * len(available)) % len(available)]
    recent.append(idx)
    if len(recent) > 1:
        recent.pop(0)
    return opts[idx]

# ── 单次转盘 ──

def _do_spin(st, rng, bet_type, bet_num, bet_payout, bet_label, bet_amount):
    result = rng.rint(0, 36)

    if bet_type == "straight":
        won = result == bet_num
    else:
        won = _BETS[bet_type][0](result)

    st["coins"] -= bet_amount
    if won:
        payout = bet_amount * (bet_payout + 1)
        st["coins"] += payout
        win = bet_amount * bet_payout
    else:
        win = 0

    st["spins"] += 1
    st["wagered"] += bet_amount
    st["won"] += win
    if win > st["biggest"]:
        st["biggest"] = win
    st["streak"] = (max(st["streak"], 0) + 1) if won else (min(st["streak"], 0) - 1)

    is_straight_win = bet_type == "straight" and won
    new_achs = _check_achs(st, win, is_straight_win, result == 0)

    return result, won, win, new_achs

# ── 主入口 ──

def cmd(text="help"):
    text = text.strip()
    parts = text.split()
    c = parts[0].lower() if parts else "help"
    st = _load()

    if c == "help":
        return (
            "🎡 轮盘赌。球落在 0-36 的哪个数字？\n"
            "下注方式：\n"
            "  spin red [金额]      红（×1）\n"
            "  spin black [金额]    黑（×1）\n"
            "  spin odd [金额]      奇（×1）\n"
            "  spin even [金额]     偶（×1）\n"
            "  spin low [金额]      小 1-18（×1）\n"
            "  spin high [金额]     大 19-36（×1）\n"
            "  spin d1 [金额]       第一打 1-12（×2）\n"
            "  spin d2 [金额]       第二打 13-24（×2）\n"
            "  spin d3 [金额]       第三打 25-36（×2）\n"
            "  spin [0-36] [金额]   单个数字（×35）\n"
            "  spin [类型] [金额] [N]  连转 N 次\n\n"
            "  balance / achievements / bailout\n"
            f"\n💰 余额 {st['coins']} 币\n"
            "🟢 0 通杀红黑奇偶大小。押单号才能中 0。"
        )

    if c in ("balance", "status"):
        net = st["won"] - st["wagered"]
        sk = st["streak"]
        sk_s = f"连胜 {sk}" if sk > 0 else f"连输 {-sk}" if sk < 0 else "—"
        return (
            f"💰 余额 {st['coins']} 币\n"
            f"🎡 转了 {st['spins']} 次 ｜ 下注 {st['wagered']} ｜ 赢 {st['won']}\n"
            f"📈 盈亏 {'+' if net >= 0 else ''}{net} ｜ 最大单笔 {st['biggest']}\n"
            f"🔥 {sk_s} ｜ 成就 {len(st['achs'])}/{len(_ACHS)}"
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
        if st["coins"] > 50: return f"还有 {st['coins']} 币。"
        if st["bailout"] == today: return "今天领过了。"
        st["coins"] += 100
        st["bailout"] = today
        _save(st)
        return f"荷官叹口气。+100 币。\n💰 余额 {st['coins']} 币"

    if c == "spin":
        if len(parts) < 2:
            return "押什么？例：spin red 50 / spin 17 50"

        bts = parts[1].lower()
        bet_amount = 10
        count = 1
        bet_num = None
        bet_type = None
        bet_payout = 0
        bet_label = ""

        try:
            num = int(bts)
            if 0 <= num <= 36:
                bet_num = num
                bet_type = "straight"
                bet_payout = 35
                bet_label = f"{num} {_sym(num)}"
            else:
                return "数字 0-36。"
        except ValueError:
            if bts in _BETS:
                _, payout, label = _BETS[bts]
                bet_type = bts
                bet_payout = payout
                bet_label = label
            else:
                return f"不认识「{bts}」。spin help 看押注方式。"

        if len(parts) >= 3:
            try: bet_amount = int(parts[2])
            except: return f"看不懂金额：{parts[2]}"
        if len(parts) >= 4:
            try: count = min(max(int(parts[3]), 1), 20)
            except: pass

        if bet_amount < 1: return "最少 1 币。"
        if bet_amount > st["coins"]: return f"不够！你有 {st['coins']} 币。"
        if bet_amount * count > st["coins"]:
            mx = st["coins"] // bet_amount
            return f"不够转 {count} 次。最多 {mx} 次。"

        rng = _Rng(st["seed"], st["calls"])
        all_achs = []

        if count == 1:
            result, won, win, new_achs = _do_spin(
                st, rng, bet_type, bet_num, bet_payout, bet_label, bet_amount)

            st["seed"] = rng.state
            st["calls"] = rng.calls
            _save(st)

            out = ["🎡 球在轮盘上跳动……", ""]
            out.append(f"   {_sym(result)} {result}  {_cn(result)}")
            out.append("")

            if won:
                out.append(f"   你押了 {bet_label} → ✅")
                out.append(f"   下注 {bet_amount} × {bet_payout} = 💰 +{win} 币！")
                if bet_type == "straight":
                    flv = _rl_pick("number_win", rng)
                elif st["streak"] >= 3:
                    flv = _rl_pick("streak_win", rng)
                else:
                    flv = _rl_pick("color_win", rng)
                if flv:
                    out.append(f"   {flv}")
            else:
                out.append(f"   你押了 {bet_label} → ❌  -{bet_amount} 币")
                if result == 0 and bet_type in ("red","black","odd","even","low","high"):
                    flv = _rl_pick("zero", rng)
                elif bet_num is not None and _is_neighbor(result, bet_num):
                    flv = _rl_pick("near_miss", rng)
                elif st["streak"] <= -5:
                    flv = _rl_pick("streak_lose", rng)
                elif bet_type == "straight":
                    flv = _rl_pick("number_lose", rng)
                else:
                    flv = _rl_pick("color_lose", rng)
                if flv:
                    out.append(f"   {flv}")

            for a in new_achs:
                out.append(a)
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['spins']} 次")
            return "\n".join(out)

        else:
            total_w = 0
            total_b = 0
            highlights = []
            actual = 0

            for i in range(count):
                if st["coins"] < bet_amount:
                    highlights.append(f"  第 {i+1} 次余额不足，停。")
                    break

                result, won, win, na = _do_spin(
                    st, rng, bet_type, bet_num, bet_payout, bet_label, bet_amount)
                actual += 1
                total_b += bet_amount
                total_w += win
                all_achs.extend(na)

                if won:
                    highlights.append(f"  #{i+1} {_sym(result)} {result} → ✅ +{win}")

                if bet_num is not None and not won and _is_neighbor(result, bet_num):
                    highlights.append(f"  #{i+1} {_sym(result)} {result}……差一格！")

            st["seed"] = rng.state
            st["calls"] = rng.calls
            _save(st)

            net = total_w - total_b
            out = [f"连转 {actual} 次 × {bet_amount} 币（押 {bet_label}）："]
            if highlights:
                out.extend(highlights)
            else:
                out.append("  全部没中 💨")
            out.append(f"总下注 {total_b} ｜ 净{'赢' if net >= 0 else '亏'} {abs(net)}")
            for a in all_achs:
                out.append(a)
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['spins']} 次")
            return "\n".join(out)

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
