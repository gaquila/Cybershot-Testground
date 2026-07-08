# Cybershot-Testground

Simulation code for **Cybershot Gladiators**, a 2–5 player team-based racing card game. This repo contains a Monte-Carlo engine, an archetype-viability harness, and a prototype layer for the drafted "Special Tactics" cards. It is a **design/balance tool**, not the game itself.

Five stats drive everything: **Lethality (L), Mitigate (M), Speed (S), Vitality (V), Willpower (W)** — indices 0–4.

---

## The three files

### `cybershot_sim.py` — the canonical engine
The single source of truth. A deterministic Monte-Carlo simulator: it drafts teams from a shared pool, runs them along a track (traverse → breach gates → fight → breach the Final Vault → extract), and reports health metrics (game length, snowball, win-rate correlations per stat, timeouts, etc.).

**Configs:**
- `V5_CONFIG()` — the validated V5 baseline. **Preserved bit-exact** as a regression reference; do not change its output.
- `V6_CONFIG(track_layout="standard9" | "short7")` — the current canon. Differs from V5 by: 11-card personal deck (T11a), ability cap removed (alarm retained), Final Vault breach = 20, Rule 1 (brace lost on move), Rule 2 (adjacent attacks −2 Lethality, negated by the Ranged tag), and an optional 7-location track.

Every V6 change in the file is marked with a `# V6` comment (grep `# V6` to see them all). The engine stays **pristine** — experimental content lives in the harness, not here.

**Run a config:**
```python
import cybershot_sim as C, random
C.PRUNED = {'RecoilHarness','StaticCloak','RedlineArray','Caltraps'}  # gear excluded from the draft pool
rng = random.Random(1)                                   # ONE rng per batch — never re-seed inside a loop
res = [C.play_game(C.V6_CONFIG("standard9"), rng) for _ in range(1000)]
print(C.summarize(res, C.V6_CONFIG("standard9"))["avg_rounds"])
```

**Gotchas:**
- Create `random.Random(seed)` **once per batch**, never inside a list comprehension (that re-seeds every game identically → degenerate results).
- `N_LOC` is set per game inside `play_game` from the built track (9 or 7). `pooled()` calls `gear_temp(track=None)` mid-game, so vault checks rely on `N_LOC`, not a live `track`.
- `extract_hold_wr` is `nan` under `V5_CONFIG` (no extraction counter); `nan != nan`, so don't treat it as a regression mismatch.

### `special_harness.py` — the Special Tactics prototype layer
A **runtime monkey-patch layer** over the engine that implements the 17 drafted "Special Tactics" cards (reusable maneuvers shuffled into the personal deck). This is a **sandbox**: the cards are a prototype heading to physical playtest, deliberately kept out of the canonical engine. It leaves `cybershot_sim.py` untouched at rest.

**Contains:** the card registry (`SPECIAL_CARDS`, with `V6_SET` = the 17 canon cards), their resolvers, draftability (adds specials to the pool with a `DVAL` draft value ∝ measured win-lift), a per-location round metric, and the Smokescreen ranged-immunity effect. Cap removal and Rules 1 & 2 are **not** here anymore — the V6 engine owns them.

**Use it:**
```python
import special_harness as H
H.install()                 # patch the engine
H.reset()
H.HS.force = {0: ["ADV_sapstrike"]}                 # force a card into team 0 (per-card testing)
# ...or draft the whole pool realistically:
H.HS.pool_enabled = set(H.V6_SET); H.HS.pool_copies = 1; H.HS.max_specials = 2
# run games with V6_CONFIG, then:
H.uninstall()               # restore canon
```
When off (`H.reset()` with nothing forced/enabled), the harness is **bit-exact inert** — the engine behaves exactly as if it weren't installed.

### `archetype_test.py` — attribute-viability harness
Pits one **stat-specialist** team (Hacker=W, Cannon=L, Speed=S, Fortress=M+V) at three intensities against three balanced opponents, and reports the specialist's win-rate vs the 0.25 baseline. Answers "is specializing in stat X viable, or punished?"

**Note:** it imports engine functions by name (`from cybershot_sim import make_pool, card_value, build_team, ...`), so those names are bound at import time. To run it **with the harness** (cards live), rebind them (`archetype_test.make_pool = cybershot_sim.make_pool`, etc.) and add a `biased_value` fallback that returns normal `card_value` for `card["kind"] == "special"` (specials have no stat line to bias on).

---

## Typical workflow
1. Change a rule/config in `cybershot_sim.py` (or a card in `special_harness.py`).
2. Verify `V5_CONFIG()` is still **bit-exact** to the pristine reference (regression guard).
3. Run the relevant harness; read the health metrics (length first — it's the #1 concern).
4. Scale runs to the question: 1k games for a quick read, 3× seeds for stability.

## Interpreting results — bot limitations
The AI is **greedy** (no lookahead). It heals only *reactively*, never proactively or to-revive; it can't set up brace-timing or cross-card combos. So trust metrics for **pacing, snowball, and tempo/draw/attack cards**, but treat low numbers for **heal cards, defensive/Mitigate-timing combos, and Rule 1** as *unmeasured*, not *bad*. Those need human playtest.
