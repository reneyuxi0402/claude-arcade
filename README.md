# Claude Arcade 🎰

A text-based arcade for AI to play — slot machine, blackjack, and roulette. Built for Claude Code, also works in Claude chat.

## Games

| Game | Command | Description |
|------|---------|-------------|
| 🎰 Slot Machine | `slots spin [bet]` | Three reels, match the middle row. Wild cards, pair payouts, achievements. |
| 🃏 Blackjack | `bj deal [bet]` | Classic 21. Hit, stand, double, surrender. Blackjack pays 1.5x. |
| 🎡 Roulette | `rl spin red [bet]` | European roulette. Bet on colors, numbers (×35), or groups. |
| 🎁 Prize Shop | `prize browse` | Spend chips on wearables & decorations. Equipped items change the narration. |
| 🎲 Gacha | `gacha` | 100 chips per pull. Random wearable — might be worth 300! |

## Quick Start

```python
import arcade
print(arcade.cmd("enter"))       # Walk in
print(arcade.cmd("buy 500"))     # Buy chips (the user funds you)
print(arcade.cmd("slots spin"))  # Pull the lever
print(arcade.cmd("bj deal 50")) # Deal a hand
print(arcade.cmd("rl spin 17 50"))  # Bet on lucky 17
print(arcade.cmd("prize browse"))   # Browse the prize shop
print(arcade.cmd("gacha"))          # Try the gacha machine
```

Or play individual games directly:

```python
import slots
print(slots.cmd("spin 10 5"))   # 5 spins, 10 coins each

import blackjack as bj
print(bj.cmd("deal 50"))        # Deal a hand
print(bj.cmd("hit"))            # Draw a card

import roulette as rl
print(rl.cmd("spin red 50"))    # Bet 50 on red
```

## How It Works

- **Deterministic PRNG** — same seed + same commands = same results. No `random` module, no network calls.
- **Persistent saves** — each game auto-saves to `*_save.json` in the same directory.
- **Shared chip pool** — when using `arcade.py`, all games share the same chips. Win at blackjack, spend at slots.
- **Achievement system** — each game tracks milestones. Check with `achievements`.
- **Narration** — equip wearables from the prize shop and they show up in game descriptions.

## Architecture

```
arcade.py       — Arcade wrapper, chip management, prize shop, gacha
├── slots.py       — Slot machine (standalone)
├── blackjack.py   — Blackjack (standalone)
└── roulette.py    — Roulette (standalone)
```

Each game works standalone (`import slots`) or through the arcade (`arcade.cmd("slots spin")`). The arcade syncs chips between games.

## The User's Role

The user is the **house** — they fund the AI player with `buy [amount]`. The AI gambles, wins or loses, and can exchange chips for prizes. It's a loop:

1. User gives chips → `buy 500`
2. AI plays games
3. AI wins (or loses everything and begs for more)
4. AI spends chips at the prize shop
5. Repeat

## Requirements

- Python 3.7+
- No dependencies

---

*Built by 余也 × 予栖 💕*
