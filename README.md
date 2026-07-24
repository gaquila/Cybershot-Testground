# Cybershot-Testground

Simulation code for **Cybershot Gladiators**, a 2–5 player team-based racing card game (optimized for 4). This repo is a **design/balance tool**, not the game. Five stats drive everything: **Lethality (L), Mitigate (M), Speed (S), Vitality (V), Willpower (W)** — indices 0–4.

---

## ⚠️ READ FIRST — the engine says "V6", but canon is V7-in-the-harness

`cybershot_sim.py` still calls itself "V6" internally. **The live design is V7**, living in the harness layer (`v7.py` + `weights_v7.py`), *not* in the engine. To run current canon you install those over the pristine engine. Do **not** treat `V6_CONFIG` as canon.

**The one number that anchors everything:** the pre-V7 draft (`winchester`) fielded only **~2.9 of 4 gladiators per team**, at every player count, in V5 and V6 alike. The game is designed for **4**. This single bug tainted every *absolute* metric the project ever produced (length, timeouts, stat correlations, snowball). It is fixed in `v7.py`. Any result older than the V7 arc is suspect in its absolutes; relative comparisons between equally-handicapped teams mostly survive.

**To just run the game at canon, use the Standard Sim:**
```python
import standard_sim as SS
SS.run()                    # full game, all layers, 3p/4p/5p, std9
```

---

## The layer cake (install order matters)

```
cybershot_sim.py          pristine engine (mechanics). NEVER edited; everything patches at runtime.
    + v7.py               V7 canon config + draft fix + rule levers        install() FIRST
    + weights_v7.py       recalibrated stat valuation (+ Willpower curve)   install() after v7
    + v8_cards.py         V8 candidate content (new chars / gear / tactics) install() after weights, before compose
    + special_harness.py  17-card Special Tactics layer (+ V8 tactics)      via compose.py, LAST
        via compose.py    re-points the harness so it CHAINS on top of v7/weights
                          instead of reverting them (it captures pristine refs at import)
```

`standard_sim.py` wires all of this correctly for you. If you compose by hand, the order and the `compose` shim are mandatory — see "Gotchas".

---

## File map

### Canonical engine (pristine)
- **`cybershot_sim.py`** — deterministic Monte-Carlo engine, single source of truth for *mechanics*. `V5_CONFIG()` is the bit-exact regression reference (never change its output); `V6_CONFIG(...)` is the pre-V7 base that V7 inherits from.

### V7 canon layer (install to get current canon)
- **`v7.py`** — `V7_CANON(track_layout)` = the **LOCKED** canon (validated across the steps 2–7 battery). Two-part draft (`v7_draft`) guarantees 4 gladiators; FILO turn order with highest-Speed-plays-last round 1; Volatile Trench hazard; and the full **lever bank** for anything still under test, via `v7.LEVERS[...]` or `dataclasses.replace(cfg, ...)`. Install FIRST.
- **`weights_v7.py`** — recalibrated `STAT_WEIGHTS` (flat `[L .94, M 1.13, S .88, V .61, W 0]`) + the **saturating Willpower curve** `Vwill(w)`. Patches `card_value`, `team_strength`, `build_team`. Install after `v7`.

### The Standard Sim (the everyday instrument)
- **`standard_sim.py`** — one call = full game, all layers on, at 3p/4p/5p. `SS.run()`, `SS.run(extra_specials=["ADV_new"])` to test a candidate card, `SS.battery()` for raw dicts. Uses the **12-card Special Tactics core** (the 5 attack cards excluded — see Bot limitations). This is what every new card/tweak gets run through. **Reports the PACE TRIPLE** — `median_rounds` + `finisher_mean` + `p90_rounds` alongside `timeout_rate` — because `avg_rounds` blends typical length with the 100-round deadlock tail (a timed-out game contributes a flat `max_rounds`). Read median/finisher for length, timeout/p90 for the deadlock tail; never one without the other. (Typical canon game ≈ 21 rounds; `avg_rounds` ≈ 26–30 is the tail talking.)
- **`compose.py`** — the shim that makes `special_harness` chain on top of `v7`+`weights_v7` (re-points its import-time `_orig_*` at the live functions) AND threads enabled specials into the v7 gear draft (v7 builds its own pool, so patching `make_pool` alone does NOT inject specials). Required whenever specials run over v7. `standard_sim` uses it internally.

### Measurement harnesses
- **`calibrate_weights.py`** — recomputes `STAT_WEIGHTS` by **seat-rotated perturbation** on mirror teams (rotation cancels a ~±3pp structural seat bias). Produced `weights_v7.py`'s numbers. Run over `v7`.
- **`archetype_v7.py`** — archetype viability on the V7 draft (biased two-part draft → real 4-gladiator teams, seat-rotated). **Use this, not archetype_v6**, for V7. Imports `INTENSITY` from `archetype_v6`.
- **`archetype_v6.py`** — the V6-correct archetype harness (fixes `archetype_test.py`'s V5-isms). Superseded by `archetype_v7` for V7 canon because it drafts with the old winchester (~2.9 glads); kept for history/regression AND because it holds the `ARCHETYPES` / `INTENSITY` constants `archetype_v7` imports. **`INTENSITY` rescaled `{5,15,45}` → `{0.6,1.5,3.0}`** (the bias term is `strength*stat_contrib` ADDED to card_value; at 45 it swamped the weights_v7-compressed gear spread and made every archetype look non-viable). Validated to reproduce the step-5 picture: Fortress strongest ~0.33 WR / lift ~1.26, extremes taxed, Speed weakest.
- **`build_bias.py`** — makes the greedy bot play *to its build* (tilted `aggro`), to test whether an archetype weakness is real or a bot that can't play it. `gain=0.0` bit-exact inert.
- **`special_harness.py`** — the 17-card Special Tactics layer. `V6_SET` = the 17 codes; `SPECIAL_CARDS` also holds V8 tactics added by `v8_cards`. Must be composed via `compose.py` when running over v7.

### V8 candidate content layer
- **`v8_cards.py`** — the V8 card set (new characters, loadouts, equipment, tactics) added ON TOP of the pristine engine by wrapping — same install/uninstall/inert discipline as every other layer. `install()` AFTER v7+weights, BEFORE `compose.install_harness_over_live()`; uninstall in reverse. Adds 8 characters (Feratu/Sephira/Vulturus/Baal wired; Stephenos/Finch/Enigma/Pythia are stat-body-only — their reactive/info abilities are **playtest-only, not modeled**), re-quirks Jayred (`night_thief` → `saboteur`), 2 loadouts (Trailblazer, Bloodletter), 3 equipment (PowerCord, PanicShield, OverdriveCell), and 6 tactics (Aegis, SecondWind, Establish, Measure, SowChaos, Gambit). Bot-blind portions (stack reorder/shuffle, reactive branches, information) are `#APPROX`/`n/m` — flagged inline. `DEBUG=True` enables per-ability fire-counters (`_COUNTS`). V5 bit-exact after an install/uninstall cycle; screened cursorily (median/timeout/snowball/lift held, no dominant new build).

### Experiment records (findings, not part of the live stack)
- **`heal_experiment.py`** — heal-to-revive lever. Finding: forcing revive 0.6→1.0 does ~nothing to length.
- **`p1_decomp.py`** — decomposition proving the attack-card length tax is ~77% combat friction, ~22% half-speed, ~0 stagger (healing can't dissolve it). `main()`-guarded.

### Superseded — do NOT use
- **`archetype_test.py`** — pre-V6 V5-isms; use `archetype_v7`.
- A standalone `draft_fix.py` (two-part draft) once existed; it is now folded into `v7.py`. Do not reintroduce a second draft path.

---

## LOCKED V7 canon

| Area | Setting | Basis |
|---|---|---|
| Character draft | mini-winchester (deal 4, take 1, pass) → exactly 4 | guarantees 4; snake ~= but higher skill (feel-test) |
| Gear/tactics draft | 10-card hands → 16 cards/player | hand=8 measured slightly worse |
| Draft pool | 1 of each (58 unique: 17 loadout + 24 equip + 17 tactics) + random dup top-up | duplicates are fine |
| First-round order | highest-Speed team plays LAST (resolves first, FILO) | free Speed buff |
| Breach | **Willpower only** (`speed_breach_frac=0.0`) | Speed contribution spikes timeouts, doesn't rehab Speed |
| Downed | contribute **50%** of stats, then team speed halved (floor 1) | best flavor; 100% too weak |
| Stagger | **OFF** (`down_stagger=0`) | shorter, best lift; complexity for negative value |
| Slipstream | **ON** (`slipstream_bonus=3`) | the one anti-snowball mechanic that measurably earns it |
| First-entry penalty | **+2** (`first_entry_penalty=2`) | +0 crashed lead-changes; +2 keeps them ~4.7 |
| Breach disruption | **OFF** (`hack_disrupt="none"`) | `freeze` bought nothing |
| Ranged | any direction, −2 Lethality adjacent unless standing Ranged glad | (V6 Rule 2) |
| Special Tactics | **12-card core** (all V6_SET minus the 5 attack-tagged cards) | attack cards toxic to pace/snowball at every player count |

Measured canon state (4p std9): **~26 rounds, ~6% timeouts, snowball concentration ~0.485, draft-skill lift ~1.3×.** 5p is the healthiest count; 3p is the mildest snowball outlier.

Roster: need 4×players characters (3p=12, 4p=16, 5p=20). The base engine owns 17; **`v8_cards` adds 8 more → 25**, which retires the 5p duplicate-gladiator problem (cursory battery showed 5p deadlock 10.4%→7.8% with the V8 roster). `v7._char_pool` still random-dups if a roster is ever short.

---

## Recalibrated stat valuation

Old `STAT_WEIGHTS [0.90,1.68,0.38,0.73,1.01]` were fitted on the broken draft (team size leaked into every stat). New (in `weights_v7.py`):
- **Flat** `[L 0.94, M 1.13, S 0.88, V 0.61, W 0.0]` — measured per-point win-value, normalised so a typical point ≈ 1.0. **W slot is 0.0 on purpose**; Willpower value comes entirely from the curve.
- **Willpower** = saturating curve `Vwill(w) = (1/0.045)·0.461·w/(w+0.352)`, valued on the margin. Marginal: 1st ≈ 7.6, 2nd ≈ 1.1, 3rd ≈ 0.46 … → Willpower is a *threshold you clear* (enough to breach), not a stack.
- Caveats: weights are **bot-relative** (a human may get more from Speed) and **config-relative** (re-measure after any breach-formula / track change).

---

## Gotchas (all live — these bit us this arc)
- **One `random.Random(seed)` per BATCH.** Never `random.Random(s)` inside the per-game loop/comprehension — it re-seeds every game and collapses the sample (you'll see ~17 rounds / ~1.5 lead-changes and every batch identical). The single easiest way to produce garbage.
- **Compose order for specials:** `v7.install()` → `weights_v7.install()` → `compose.install_harness_over_live()` → `compose.enable_specials_in_v7_draft()`. `special_harness` captures pristine `_orig_*` at import and will silently REVERT v7+weights if installed naively. Just use `standard_sim`.
- **Specials must be threaded into the v7 draft.** v7 builds its own gear pool; patching `make_pool` alone does not inject specials. `compose.enable_specials_in_v7_draft()` handles it.
- **Harnesses that bypass `play_game`** (calibration, archetype) must set `C.ABILITY_CAP_ON = cfg.ability_cap` and `C.N_LOC = len(track)` themselves, or they silently run V5-capped / 9-location rules.
- **Seat bias:** identical mirror teams do NOT win 1/n by seat (~±3pp seat-0 vs last). Any perturbation/mirror/archetype measurement must rotate the subject across seats.
- **Always** verify `V5_CONFIG()` output is unchanged after any new patch (bit-exact regression), and that a new harness is bit-exact inert at its neutral setting.
- `extract_hold_wr` / `yomi_richness` are `nan` under configs lacking those counters; `nan != nan`, don't flag as a mismatch.

## Bot limitations (what the sim CANNOT measure)
The AI is **greedy** (no lookahead): heals only reactively (never to-revive), can't time brace/defends, can't sequence combos, never chooses to double-breach, and plays attack cards bluntly (swings whenever able). Trust metrics for **pacing, snowball, draw/tempo economy, stat balance**. Treat weak numbers for **heal/defensive/timing/combo/attack cards** as *unmeasured*, not *bad* — carry to physical playtest ("bot-blind keepers"). The 5 attack cards are excluded from the Standard Sim core for exactly this reason: the sim sees only their worst case.
