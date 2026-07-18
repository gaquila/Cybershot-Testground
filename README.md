# Cybershot-Testground

Simulation code for **Cybershot Gladiators**, a 2–5 player team-based racing card game. This repo contains a Monte-Carlo engine, an archetype-viability harness, and a set of runtime harness layers for drafting, rules-levers, and stat calibration. It is a **design/balance tool**, not the game itself.

Five stats drive everything: **Lethality (L), Mitigate (M), Speed (S), Vitality (V), Willpower (W)** — indices 0–4.

---

## ⚠️ Read this first — where the project actually is (V7 arc)

The engine file (`cybershot_sim.py`) still calls itself "V6". **The live design is V7**, and V7 lives in the harness layer (`v7.py`), *not* in the engine. Do not treat `V6_CONFIG` as canon anymore. Two major issues were found and fixed at the harness level this arc:

1. **The draft was broken the entire time (V5 and V6).** Every config used `draft_type="winchester"`, which shuffles characters into one big pool and only deals a subset — so teams fielded **~2.9 of 4 gladiators**, at every player count. The game was designed for **4 gladiators per team**. Fixed in `v7.py` (`v7_draft`): a character draft that guarantees exactly 4, then a gear/tactics winchester. **Any pre-V7 absolute metric (length, timeouts, stat correlations) was measured on crippled teams and is not trustworthy.** Relative comparisons between equally-handicapped teams mostly survive; absolutes do not.
2. **`STAT_WEIGHTS` was calibrated on the broken draft.** Recalibrated by perturbation in `weights_v7.py`. Willpower turned out to be a near-step function (all value in the first point), so it is now valued by a saturating curve, not a flat weight.

**To run anything at current canon:** install `v7` (and usually `weights_v7`) over the engine. See "V7 quickstart" below.

---

## File map

### Canonical engine
- **`cybershot_sim.py`** — the deterministic Monte-Carlo engine. Single source of truth for *mechanics*. Stays **pristine**; all experiments monkey-patch it at runtime and restore it. Configs: `V5_CONFIG()` (bit-exact regression reference — never change its output) and `V6_CONFIG("standard9"|"short7")`.

### V7 canon layer (install these to get current canon)
- **`v7.py`** — proposed V7 canon config `V7_CANON(track_layout)` **plus the full lever bank**. Encodes the draft fix, the FILO turn order with the speed-first-round rule, the Volatile Trench hazard, and every rule George flagged for testing (breach formula, downed-contribution A/B/C, stagger, slipstream, first-entry penalty, breach disruption, gear hand size, draft mode). Everything toggled via `v7.LEVERS[...]` or `dataclasses.replace(cfg, ...)`. `install()` before `special_harness.install()` if using both.
- **`weights_v7.py`** — recalibrated `STAT_WEIGHTS` (flat for L/M/S/V) + the **saturating Willpower curve** `Vwill(w)`. Patches `card_value`, `team_strength`, and `build_team`'s character sort so the bot values Willpower on the margin. `install()`/`uninstall()`; restores old weights bit-exact.

### Measurement harnesses (install over the engine as needed)
- **`calibrate_weights.py`** — recomputes `STAT_WEIGHTS` by **seat-rotated perturbation** on mirror teams (add +N of one stat, measure win-lift). Rotates the perturbed team across all seats to cancel the ~±3pp structural seat bias. Run *on top of* `v7`. This is how `weights_v7.py`'s numbers were produced.
- **`archetype_v6.py`** — V6/V7-correct archetype-viability harness. **Supersedes `archetype_test.py`**, which has latent V5-isms (defines its own `V5()`, calls `build_track()` without `vault_breach=`/`layout=`, and bypasses `play_game()` so `ABILITY_CAP_ON`/`N_LOC` never get set). `archetype_v6.py` fixes all three, sets the globals itself, and keeps a `legacy_track=True` mode that reproduces the old harness **bit-exact** as a regression guard.
- **`build_bias.py`** — makes the greedy bot play *to its build* (Lethality teams attack more, Speed teams race more) via a stat-tilted `aggro`. Used to test whether an archetype's weakness is real or just a bot that can't play it. `gain=0.0` is bit-exact inert.
- **`special_harness.py`** — the 17-card Special Tactics prototype layer (unchanged from prior arcs). Runtime patch; `V6_SET` = the canon 17. Bit-exact inert when off.

### Experiment records (the scripts that produced findings)
- **`heal_experiment.py`** — Phase-1 heal-to-revive lever. Finding: forcing revive 0.6→1.0 does ~nothing to length.
- **`p1_decomp.py`** — the decomposition that explained it: the attack-card length tax is ~77% pure combat friction, ~22% half-speed, ~0 stagger. **Healing cannot dissolve the length tax** (overturns a prior assumption).

### Superseded / do not use as canon
- **`archetype_test.py`** — kept for history; use `archetype_v6.py`.
- Two-part draft logic once lived in a standalone `draft_fix.py`; it is now folded into `v7.py` (`v7_draft`). Do not reintroduce a second draft path.

---

## V7 quickstart

```python
import random, statistics
import cybershot_sim as C
import v7, weights_v7 as WT

C.PRUNED = {'RecoilHarness','StaticCloak','RedlineArray','Caltraps'}
v7.install()          # draft fix + turn order + hazard + levers
WT.install()          # recalibrated weights + Willpower curve

cfg = v7.V7_CANON("standard9")          # tentative V7 canon
rng = random.Random(1)                  # ONE rng per batch (see gotchas)
res = [C.play_game(cfg, rng) for _ in range(1000)]
print(C.summarize(res, cfg)["avg_rounds"])

WT.uninstall(); v7.uninstall()          # engine is pristine again
```

**Flip a lever** (test vs canon):
```python
from dataclasses import replace
cfg = replace(v7.V7_CANON("standard9"), speed_breach_frac=1.5)   # config-backed lever
v7.LEVERS["gear_hand_size"] = 8                                  # module lever
cfg = v7.set_down_contrib(v7.V7_CANON("standard9"), 0.0)         # downed contribution mode C
```

---

## V7 canon (tentative) vs levers

CANON is the tentative lock; each lever is an alternative queued for testing.

| Area | CANON | Levers to test |
|---|---|---|
| Character draft | mini-winchester (deal 4, take 1, pass) → exactly 4 glads | `random`, `snake` |
| Gear/tactics draft | 10-card hands → 16 cards/player | 8-card hands → 12/player |
| Draft pool | 1 of each (58 unique: 17 loadout + 24 equip + 17 tactics) + random dup top-up to fill the deal | — |
| First-round order | highest-Speed team plays **last** (resolves first, FILO) | off |
| Volatile Trench | attacked there → +1 direct damage | off |
| Breach formula | **Willpower only** (`speed_breach_frac=0.0`) — premium breach stat by design | `1.5`, `0.5` |
| Action repeats | 1 of each type/turn, Move only ×2 | double-breach (parked — bot never chooses it) |
| Downed contribution | **B: 50%** of stats, then team speed halved (floor 1) | A: 100%, C: 0% |
| Stagger | on (+1 traversal on new down) | off |
| Slipstream | on (+3 speed/location behind leader) | off |
| First-entry penalty | +3 traversal (first team into a location) | +2, 0 |
| Breach disruption | **off** | `freeze` |
| Ranged | any direction, −2 Lethality from adjacent unless a standing Ranged glad | (canon) |

Roster note: 4×players characters needed (3p=12, 4p=16, 5p=20; we own 17). `v7._char_pool` tops up short rosters with random duplicate characters. 5p needs +3 real designs to avoid duplicates.

---

## Recalibrated stat valuation (V7)

Old `STAT_WEIGHTS` `[0.90, 1.68, 0.38, 0.73, 1.01]` were fitted on the broken draft. New (in `weights_v7.py`):

- **Flat weights** `[L 0.94, M 1.13, S 0.88, V 0.61, W 0.0]` — measured per-point win-value, normalised so a typical point ≈ 1.0. The W slot is **0.0 on purpose**; Willpower value comes entirely from the curve.
- **Willpower** = saturating curve `Vwill(w) = (1/0.045)·0.461·w/(w+0.352)`, valued **on the margin**. Marginal per point: 1st ≈ 7.6, 2nd ≈ 1.1, 3rd ≈ 0.46, 4th ≈ 0.25, 5th ≈ 0.15. Meaning: Willpower is a **threshold you clear** (enough to breach), not a stat you stack.

Caveats to carry with any number: weights are **bot-relative** (a human may get more from Speed) and **config-relative** (re-measure after any breach-formula/track change).

---

## Gotchas (all still live)
- **One `random.Random(seed)` per batch** — never re-seed inside a loop/comprehension (degenerate results). Metrics shift with N and seed; small deltas across runs are RNG, not drift.
- **Install order**: `v7.install()` before `special_harness.install()` (both may wrap `_commit_v2`; v7 first so the harness wraps the v7 version).
- **`archetype_v6` / calibration bypass `play_game`**, so they set `C.ABILITY_CAP_ON` and `C.N_LOC` themselves. Any new harness that bypasses `play_game` must do the same or it silently runs V5-capped, 9-location rules.
- **Seat bias**: identical mirror teams do not win 1/n by seat (~±3pp seat-0-vs-last). Any perturbation/mirror measurement must rotate across seats.
- `V5_CONFIG` regression guard: patch → verify `V5_CONFIG()` output unchanged → run. Every harness here is built to be bit-exact inert at its neutral setting; keep it that way.
- **`extract_hold_wr` is `nan`** under configs without an extraction counter; `nan != nan`, so don't flag it as a mismatch.

## Interpreting results — bot limitations
The AI is **greedy** (no lookahead). It heals only reactively (never proactively/to-revive), can't set up brace-timing or cross-card combos, and never chooses to double-breach. Trust metrics for **pacing, snowball, tempo/draw/attack cards**; treat weak numbers for **heal/defensive/timing/combo cards and Rule 1** as *unmeasured*, not *bad*. Those need physical playtest.

## Test sequence (approved, in progress)
1. ✅ Recalibrate `STAT_WEIGHTS` (perturbation, V7 canon) → `weights_v7.py`.
2. ⏳ Canon baseline battery — 4p, both tracks (the new reference point).
3. Single-lever sweeps vs canon (breach → downed A/B/C → stagger → slipstream → first-entry → disruption → hand size → draft mode).
4. Interaction checks on the anti-snowball trio (stagger × slipstream × first-entry) and breach × draft.
5. Archetype viability (`archetype_v6.py`) on the winning canon.
6. Special Tactics layer re-run on real 4-gladiator teams (revisit the +36% length tax).
7. 3p / 5p battery last.
```
