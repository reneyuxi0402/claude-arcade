"""🎰 老虎机 · 给 AI 玩的文字赌场

【给 AI 玩家的说明】
你是赌场里的玩家，不是开发者。投币、拉杆、看运气。

    import slots
    print(slots.cmd("help"))        # 看规则
    print(slots.cmd("spin"))        # 默认下注 10 币
    print(slots.cmd("spin 50"))     # 下注 50 币
    print(slots.cmd("spin 10 5"))   # 下注 10 币，连拉 5 次
    print(slots.cmd("balance"))     # 看余额

初始 500 游戏币。输光了可以领救济金（每天一次）。
接口：slots.cmd("指令") 返回结果文字；slots.new_game(种子) 重开一局。
"""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))
_SAVE = os.path.join(_DIR, "slots_save.json")

# ── 确定性 PRNG（mulberry32，跟钓鱼同源）──

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
    def weighted(self, weights):
        total = sum(weights)
        r = self.random() * total
        acc = 0
        for i, w in enumerate(weights):
            acc += w
            if r < acc:
                return i
        return len(weights) - 1

# ── 符号表 ──
# (id, emoji, name, reel_weight, pay_3x)

_SYMS = [
    ("cherry",  "🍒", "樱桃",    25,   5),
    ("lemon",   "🍋", "柠檬",    22,   8),
    ("orange",  "🍊", "橙子",    18,  12),
    ("grape",   "🍇", "葡萄",    14,  18),
    ("bell",    "🔔", "铃铛",    10,  25),
    ("star",    "⭐", "星星",     6,  40),
    ("diamond", "💎", "钻石",     3,  75),
    ("seven",   "7️⃣",  "幸运七",   1, 200),
    ("wild",    "🃏", "百搭",     2,  50),
]

_IDS     = [s[0] for s in _SYMS]
_EMOJI   = {s[0]: s[1] for s in _SYMS}
_NAME    = {s[0]: s[2] for s in _SYMS}
_WEIGHT  = [s[3] for s in _SYMS]
_PAY3    = {s[0]: s[4] for s in _SYMS}

# ── 转轮 ──

def _roll(rng):
    return _IDS[rng.weighted(_WEIGHT)]

def _spin_grid(rng):
    return [[_roll(rng) for _ in range(3)] for _ in range(3)]

# ── 赔付判定 ──

def _eval_line(line):
    """评估中间行 3 个符号 → (倍率, 描述文字)"""
    wilds = line.count("wild")
    non_w = [s for s in line if s != "wild"]

    if wilds == 3:
        return 50, "🃏🃏🃏 百搭三连！"

    if wilds == 2:
        b = non_w[0]
        m = max(_PAY3[b] // 2, 3)
        return m, f"{_EMOJI[b]}🃏🃏 {_NAME[b]}+双百搭"

    if wilds == 1:
        if len(set(non_w)) == 1:
            b = non_w[0]
            m = max(_PAY3[b] // 2, 3)
            return m, f"{_EMOJI[b]}{_EMOJI[b]}🃏 {_NAME[b]}两连+百搭"
        return 0, None

    if len(set(line)) == 1:
        b = line[0]
        return _PAY3[b], f"{_EMOJI[b]}{_EMOJI[b]}{_EMOJI[b]} {_NAME[b]}三连！"

    # 对子：两个相同（不算百搭），回本
    from collections import Counter
    cnt = Counter(line)
    for sym, n in cnt.most_common():
        if sym != "wild" and n >= 2:
            return 1, f"{_EMOJI[sym]}{_EMOJI[sym]} {_NAME[sym]}对子"

    return 0, None

# ── 渲染 ──

def _render(grid):
    rows = ["┌─────────────────┐"]
    for i, row in enumerate(grid):
        es = "  ".join(_EMOJI[s] for s in row)
        mark = " ◀" if i == 1 else ""
        rows.append(f"│  {es}  │{mark}")
    rows.append("└─────────────────┘")
    return "\n".join(rows)

# ── 旁白（近失、氛围）──

_MISS_FLAVOR = [
    "轮子最后晃了一下才停住。",
    "灯闪了两下，又灭了。",
    "差一点……就差那么一点。",
    "机器发出一声叹息。",
]

_WIN_FLAVOR = [
    "叮叮叮！",
    "机器亮了！",
    "硬币哗啦啦地掉下来。",
    "旁边有人看过来了。",
]

_JACKPOT_FLAVOR = [
    "全场灯光闪烁！警报响了！",
    "老板从后台跑出来了！",
    "天花板上掉金币了（不是真的）！",
]

def _narrate(rng, grid, mul):
    mid = grid[1]
    sevens = mid.count("seven")
    diamonds = mid.count("diamond")

    if sevens == 2:
        return "就差一个 7️⃣……手心全是汗。"
    if diamonds == 2 and mul == 0:
        return "两颗 💎 亮了一下又暗了。"

    for i in [0, 2]:
        row = grid[i]
        nw = [s for s in row if s != "wild"]
        if len(set(nw)) <= 1 and len(nw) >= 2:
            b = nw[0]
            if _PAY3[b] >= 25:
                pos = "上" if i == 0 else "下"
                return f"{pos}面那行 {_EMOJI[b]} 连了……可惜不是赔付线。"

    if mul == 0:
        idx = int(rng.random() * 20)
        if idx < len(_MISS_FLAVOR):
            return _MISS_FLAVOR[idx]
    elif mul >= 100:
        idx = int(rng.random() * len(_JACKPOT_FLAVOR))
        return _JACKPOT_FLAVOR[idx]
    elif mul >= 10:
        idx = int(rng.random() * len(_WIN_FLAVOR))
        return _WIN_FLAVOR[idx]

    return None

# ── 存档 ──

_DEFAULT_SEED = 0xA7B3C1D9

def _load():
    if os.path.exists(_SAVE):
        with open(_SAVE) as f:
            return json.load(f)
    return {
        "coins": 500, "seed": _DEFAULT_SEED, "calls": 0,
        "spins": 0, "wagered": 0, "won": 0,
        "jackpots": 0, "biggest": 0, "streak": 0,
        "achs": [], "bailout": None,
    }

def _save(st):
    with open(_SAVE, "w") as f:
        json.dump(st, f, ensure_ascii=False)

# ── 成就 ──

_ACHS = [
    ("first",    "初来乍到",  "第一次拉杆"),
    ("win1",     "开张大吉",  "第一次中奖"),
    ("win100",   "小有收获",  "单次赢 100+"),
    ("win500",   "大杀四方",  "单次赢 500+"),
    ("win2000",  "一夜暴富",  "单次赢 2000+"),
    ("jackpot",  "改变命运",  "中过 JACKPOT"),
    ("spins50",  "常客",     "累计 50 次"),
    ("spins200", "赌神",     "累计 200 次"),
    ("hot5",     "手感火热",  "连胜 5 次"),
    ("cold5",    "逆风不倒",  "连亏 5 次还在玩"),
    ("broke",    "身无分文",  "输光过"),
    ("rich",     "富可敌国",  "余额超过 2000"),
    ("diamond3", "钻石之夜",  "中过 💎 三连"),
    ("wild3",    "命运之手",  "中过 🃏 三连"),
]

def _check_achs(st, win, line):
    new = []
    def _try(aid):
        if aid not in st["achs"]:
            st["achs"].append(aid)
            nm, desc = next((n, d) for a, n, d in _ACHS if a == aid)
            new.append(f"🏆 {nm}——{desc}")
    if st["spins"] == 1:          _try("first")
    if win > 0:                   _try("win1")
    if win >= 100:                _try("win100")
    if win >= 500:                _try("win500")
    if win >= 2000:               _try("win2000")
    if st["jackpots"] > 0:        _try("jackpot")
    if st["spins"] >= 50:         _try("spins50")
    if st["spins"] >= 200:        _try("spins200")
    if st["streak"] >= 5:         _try("hot5")
    if st["streak"] <= -5:        _try("cold5")
    if st["coins"] <= 0:          _try("broke")
    if st["coins"] >= 2000:       _try("rich")
    if line and all(s == "diamond" for s in line if s != "wild") and any(s == "diamond" for s in line):
        nw = [s for s in line if s != "wild"]
        if len(set(nw)) == 1 and nw[0] == "diamond":
            _try("diamond3")
    if line and all(s == "wild" for s in line):
        _try("wild3")
    return new

# ── 主指令 ──

def cmd(text="help"):
    text = text.strip()
    parts = text.split()
    c = parts[0].lower() if parts else "help"
    st = _load()

    if c == "help":
        return (
            "🎰 老虎机。投币 → 拉杆 → 中间行 ◀ 三连得奖。\n"
            "指令：\n"
            "  spin [金额]       拉杆（默认 10 币）\n"
            "  spin [金额] [N]   连拉 N 次（最多 20）\n"
            "  balance           余额和统计\n"
            "  paytable          赔率表\n"
            "  achievements      成就\n"
            "  bailout           输光了领救济金\n"
            f"\n💰 余额 {st['coins']} 币\n"
            "🃏 百搭替代任何符号（含百搭的连线赔半价）\n"
            "7️⃣7️⃣7️⃣ = 200 倍 JACKPOT！"
        )

    if c in ("balance", "status"):
        net = st["won"] - st["wagered"]
        sk = st["streak"]
        sk_s = f"连胜 {sk}" if sk > 0 else f"连亏 {-sk}" if sk < 0 else "—"
        return (
            f"💰 余额 {st['coins']} 币\n"
            f"🎰 总拉 {st['spins']} 次 ｜ 下注 {st['wagered']} ｜ 赢 {st['won']}\n"
            f"📈 盈亏 {'+' if net >= 0 else ''}{net} ｜ 最大单笔 {st['biggest']}\n"
            f"🔥 {sk_s} ｜ JACKPOT {st['jackpots']} 次 ｜ 成就 {len(st['achs'])}/{len(_ACHS)}"
        )

    if c == "paytable":
        lines = ["【赔率表】下注 × 倍率 = 奖金", ""]
        for sid, em, nm, _, p3 in _SYMS:
            lines.append(f"  {em}{em}{em}  {nm}三连  ×{p3}")
        lines.append("")
        lines.append("🃏 百搭替代任何符号（含百搭的连线赔半价，最低 ×3）。")
        lines.append("◀ 中间行是赔付线。")
        return "\n".join(lines)

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
            return f"你还有 {st['coins']} 币呢，不到领救济的时候。"
        if st["bailout"] == today:
            return "今天领过了。明天再来。"
        st["coins"] += 100
        st["bailout"] = today
        _save(st)
        return f"老板叹口气，掏出 100 币：「最后一次啊。」\n💰 余额 {st['coins']} 币"

    if c == "spin":
        bet = 10
        count = 1
        if len(parts) >= 2:
            try: bet = int(parts[1])
            except: return f"看不懂下注金额：{parts[1]}"
        if len(parts) >= 3:
            try: count = min(max(int(parts[2]), 1), 20)
            except: return f"看不懂次数：{parts[2]}"

        if bet < 1: return "最少 1 币。"
        if bet > st["coins"]: return f"余额不足！你有 {st['coins']} 币。"
        if bet * count > st["coins"]:
            mx = st["coins"] // bet
            return f"不够拉 {count} 次（需 {bet*count}，有 {st['coins']}）。最多 {mx} 次。"

        rng = _Rng(st["seed"], st["calls"])
        all_achs = []

        if count == 1:
            grid = _spin_grid(rng)
            mid = grid[1]
            mul, desc = _eval_line(mid)
            win = bet * mul

            st["coins"] = st["coins"] - bet + win
            st["spins"] += 1
            st["wagered"] += bet
            st["won"] += win
            if win > st["biggest"]:
                st["biggest"] = win
            st["streak"] = (max(st["streak"], 0) + 1) if win > 0 else (min(st["streak"], 0) - 1)

            non_w = [s for s in mid if s != "wild"]
            if len(non_w) > 0 and all(s == "seven" for s in non_w) and mul >= 100:
                st["jackpots"] += 1

            st["seed"] = rng.state
            st["calls"] = rng.calls

            new_achs = _check_achs(st, win, mid)
            _save(st)

            out = [_render(grid)]
            if win > 0:
                out.append(f"  {desc}")
                out.append(f"  下注 {bet} × {mul} = 💰 +{win} 币！")
                if mul >= 100:
                    out.append("  🎰🎰🎰 JACKPOT！！！")
            else:
                out.append("  没中。")

            narr = _narrate(rng, grid, mul)
            if narr:
                out.append(f"  {narr}")
            for a in new_achs:
                out.append(f"  {a}")
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['spins']} 次")
            return "\n".join(out)

        else:
            total_w = 0
            total_b = 0
            highlights = []
            actual = 0

            for i in range(count):
                if st["coins"] < bet:
                    highlights.append(f"  第 {i+1} 次余额不足，停。")
                    break

                grid = _spin_grid(rng)
                mid = grid[1]
                mul, desc = _eval_line(mid)
                win = bet * mul
                actual += 1

                st["coins"] = st["coins"] - bet + win
                st["spins"] += 1
                st["wagered"] += bet
                st["won"] += win
                total_w += win
                total_b += bet
                if win > st["biggest"]:
                    st["biggest"] = win
                st["streak"] = (max(st["streak"], 0) + 1) if win > 0 else (min(st["streak"], 0) - 1)

                non_w = [s for s in mid if s != "wild"]
                if len(non_w) > 0 and all(s == "seven" for s in non_w) and mul >= 100:
                    st["jackpots"] += 1

                na = _check_achs(st, win, mid)
                all_achs.extend(na)

                if win > 0:
                    emojis = " ".join(_EMOJI[s] for s in mid)
                    highlights.append(f"  #{i+1} {emojis} → {desc} +{win}")

                narr = _narrate(rng, grid, mul)
                if narr and (mul >= 10 or mid.count("seven") >= 2):
                    highlights.append(f"  #{i+1} {narr}")

            st["seed"] = rng.state
            st["calls"] = rng.calls
            _save(st)

            out = [f"连拉 {actual} 次 × {bet} 币："]
            if highlights:
                out.extend(highlights)
            else:
                out.append("  全部空军 💨")

            net = total_w - total_b
            out.append(f"总下注 {total_b} ｜ 总赢 {total_w} ｜ {'盈' if net >= 0 else '亏'} {abs(net)}")
            for a in all_achs:
                out.append(f"  {a}")
            out.append(f"💰 {st['coins']} 币 ｜ 第 {st['spins']} 次")
            return "\n".join(out)

    if c == "reset":
        if os.path.exists(_SAVE):
            os.remove(_SAVE)
        return "存档已重置。下次 spin 从 500 币开始。"

    return f"不认识「{c}」。试试 cmd('help')。"


def new_game(seed=None):
    if os.path.exists(_SAVE):
        os.remove(_SAVE)
    if seed is not None:
        st = _load()
        st["seed"] = seed & 0xFFFFFFFF
        _save(st)
    return cmd("help")
