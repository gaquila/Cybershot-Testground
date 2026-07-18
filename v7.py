"""
v7.py -- proposed V7 canon + full lever bank.
=============================================
Runtime harness over cybershot_sim. The canonical engine file is NOT edited.
This encodes George's spec rulings. Everything he flagged "TEST" is a lever.

TERMINOLOGY
-----------
  CANON  = the tentative locked setting (V7_CANON()).
  LEVER  = an alternative we will measure against canon.

New levers that are NOT Config dataclass fields live in the module-level
LEVERS dict (we cannot add fields to the engine's Config without editing it).
Config-backed levers are set via dataclasses.replace() as normal.

=========================  SPEC -> IMPLEMENTATION  =========================

1. GLADIATOR DRAFT                      LEVERS["char_draft"]
   CANON "mini_winchester": deal 4 characters to each player; take 1, pass;
       4 passes -> every player ends with exactly 4. Needs exactly 4*n chars.
   LEVER "random": deal 4 characters to each player, no choice (simplest).
   LEVER "snake"  : 4 snake rounds, pick 1 each.
   Roster: 4*n characters required (3p=12, 4p=16, 5p=20; we own 17).
       Short rosters are topped up with random duplicate characters.

2. PERSONAL DECK                        (no change -- already exact)
   T11a 11-card deck, unchanged. Colours are cosmetic, not modelled.

3. GEAR WINCHESTER                      LEVERS["gear_hand_size"]
   CANON 10-card hands: take 2 & pass x4, last 2 discarded, x2 rounds
         -> 16 gear cards per player.
   LEVER  8-card hands: take 2 & pass x3, last 2 discarded, x2 rounds
         -> 12 gear cards per player.
   Pool: singleton (1 of each) per George, then RANDOM duplicate top-up to
   meet the deal. See LEVERS["gear_copies"] (1 = singleton base).
   *** See SINGLETON_WARNING below -- this does not currently reach singleton.

4. ASSEMBLY                             (already correct -- verified)
   build_team gives each gladiator 1 loadout + up to 3 equipment = 4 total.
   Exception by design: the "master_none" quirk grants a 2nd loadout.
   Start hand 4. Specials shuffle into the personal deck (harness layer).

5. FIRST-ROUND ORDER                    LEVERS["speed_first_order"]
   CANON True: on round 1 the highest-Speed team plays LAST (so its actions
       resolve FIRST under the FILO stack). Later rounds rotate as before.
   LEVER False: engine default (random initial order).

6. VOLATILE TRENCH HAZARD               LEVERS["hazard_direct_damage"]
   CANON 1: a team attacked while in a "hazard" location takes 1 direct
       damage (in addition to normal attack damage). Previously the "hazard"
       effect string was decorative -- no code consumed it.
   LEVER 0: off.

7. BREACH FORMULA                       cfg.speed_breach_frac
   CANON 0.0: breach = Willpower only. (Flavour: Speed helping you hack is
       unintuitive; George prefers it gone if the numbers allow.)
   LEVER 1.5: breach = Willpower + 1.5 x Speed  (power up Speed).
   LEVER 0.5: the old V6 value, kept for continuity comparisons.
   HEAL: a Heal action restores 1 HP (revive-first). Already exact.

8.1 ACTION REPEATS                      LEVERS["allow_double_breach"]
   CANON False: 1 of each action type per turn, EXCEPT Move (sprint = 2 moves).
   LEVER True: also allow breach+breach in one turn.

8.2 DOWNED CONTRIBUTION                 LEVERS["down_contrib"]
   Team speed is ALWAYS halved while any gladiator is down (floor 1), applied
   AFTER the downed gladiator's own contribution is counted.
   LEVER A  1.0: downed gladiators contribute 100% of all stats.
   CANON B  0.5: downed gladiators contribute 50% of all stats. (= today)
   LEVER C  0.0: downed gladiators contribute 0%.
   NOTE this fixes a latent double-dip: the engine had down_factor=0.5 for
   four stats but a SEPARATE down_speed_factor=0.5 for Speed, so a downed
   gladiator's Speed was halved and THEN the team's speed halved again.
   Here down_factor == down_speed_factor always, so the contribution mode is
   uniform across all five stats and the team-halving is the only extra step.

8.3 STAGGER                             cfg.down_stagger
   CANON 1: +1 traversal to the victim when a gladiator is newly downed.
   LEVER 0: off.

8.4 SLIPSTREAM                          cfg.slipstream_bonus
   CANON 3: +3 speed per location behind the leader (graduated).
   LEVER 0: off.

10.1 FIRST-ENTRY PENALTY                cfg.first_entry_penalty
   CANON 3: first team into a new location pays +3 traversal.
   LEVER 2: softer trailblazer tax.
   LEVER 0: off (is any anti-snowball tax still needed?).

10.2 BREACH DISRUPTION                  cfg.hack_disrupt
   CANON "none": being attacked does NOT stop your breach. (Changed from V6.)
   LEVER "freeze": being attacked at a gate/vault zeroes your breach progress
       for that turn (the old V6 behaviour; George: "probably too draconian").

10.4 RANGED                             (already canon -- no change)
   Ranged fires in any direction (ranged_forward_only=False), with -2 Lethality
   from adjacent locations unless a standing gladiator has the Ranged tag
   (adjacent_leth_penalty=2). Already V6 Rule 2.

10.5 OFF AND STAYING OFF                blue_shell, rubberband, catchup_draw,
                                        leader_draw_pen, free_attack_per_turn.

=========================  SINGLETON WARNING  =============================
George asked for 1 copy of each gear card. The deal needs 2 * n * hand_size
gear cards:
        4p @10 -> 80      5p @10 -> 100     3p @10 -> 60
        4p @ 8 -> 64      5p @ 8 ->  80     3p @ 8 -> 48
We own 17 loadouts + 24 unpruned equipment = 41 unique gear cards.
So a TRUE singleton draft is impossible at every player count; the pool is
topped up with random duplicates (~2x at 4p/10). To reach real singleton at
4p you would need ~80 unique gear designs (~+39). Flagged, not silently
papered over. LEVERS["gear_copies"] controls the base copies before top-up.
===========================================================================
"""
import inspect
from dataclasses import replace

import cybershot_sim as C

C.PRUNED = {'RecoilHarness', 'StaticCloak', 'RedlineArray', 'Caltraps'}

LEVERS = {
    "char_draft":           "mini_winchester",   # | "random" | "snake"
    "gear_hand_size":       10,                  # | 8
    "gear_copies":          1,                   # base copies before random top-up
    "speed_first_order":    True,                # highest Speed plays last, round 1
    "hazard_direct_damage": 1,                   # | 0
    "allow_double_breach":  False,               # | True
    "down_contrib":         0.5,                 # 1.0 (A) | 0.5 (B, canon) | 0.0 (C)
}

_DEFAULTS = dict(LEVERS)


def V7_CANON(track_layout="standard9"):
    """Tentative V7 canon. Inherits V6 then applies George's rulings."""
    cfg = replace(
        C.V6_CONFIG(track_layout),
        draft_type="v7",            # anything != "winchester" routes to our draft
        speed_breach_frac=0.0,      # 7  CANON: Willpower only
        hack_disrupt="none",        # 10.2 CANON: breach disruption OFF
        first_entry_penalty=3,      # 10.1 CANON
        down_stagger=1,             # 8.3 CANON
        slipstream_bonus=3,         # 8.4 CANON
        down_factor=0.5,            # 8.2 CANON B (kept in sync by set_down_contrib)
        down_speed_factor=0.5,
        ranged_forward_only=False,  # 10.4 CANON
        adjacent_leth_penalty=2,    # 10.4 CANON
    )
    return cfg


def set_down_contrib(cfg, mode):
    """8.2 -- uniform contribution across all five stats. Returns a new cfg."""
    assert mode in (1.0, 0.5, 0.0), "down_contrib must be 1.0, 0.5 or 0.0"
    LEVERS["down_contrib"] = mode
    return replace(cfg, down_factor=mode, down_speed_factor=mode)


# ----------------------------------------------------------------- drafting
def _char_pool(rng, n):
    """Exactly 4*n characters; random duplicates if the roster is short."""
    names = list(C.CHARACTERS)
    pool = [{"kind": "char", "name": nm} for nm in names]
    need = 4 * n
    while len(pool) < need:
        pool.append({"kind": "char", "name": rng.choice(names)})
    rng.shuffle(pool)
    return pool[:need]


def _gear_pool(rng, n, hand_size, include_specials=False, special_names=None):
    """Singleton base (gear_copies) of loadouts + equipment (+ optional special
    tactics), then a few RANDOM duplicate copies to fill the deal.

    Unique draftable base = 17 loadouts + 24 equipment (+ 17 specials) = 41/58.
    Deal needs 2*n*hand_size; the shortfall is topped up with random dups."""
    base = []
    for _ in range(LEVERS["gear_copies"]):
        for nm in C.LOADOUTS:
            if nm not in C.PRUNED:
                base.append({"kind": "loadout", "name": nm})
        for nm in C.EQUIPMENT:
            if nm not in C.PRUNED:
                base.append({"kind": "equip", "name": nm})
        if include_specials and special_names:
            for nm in special_names:
                base.append({"kind": "special", "name": nm})
    need = 2 * n * hand_size
    pool = list(base)
    while len(pool) < need:
        pool.append(dict(rng.choice(base)))
    rng.shuffle(pool)
    return pool[:need]


def v7_draft(cfg, rng, drafters):
    n = cfg.n_players
    picks = [[] for _ in range(n)]
    mode = LEVERS["char_draft"]

    # ---- 1. characters -> exactly 4 each ----
    chars = _char_pool(rng, n)
    if mode == "random":
        for i in range(n):
            for _ in range(4):
                picks[i].append(chars.pop())
    elif mode == "snake":
        order = list(range(n))
        for r in range(4):
            for i in (order if r % 2 == 0 else order[::-1]):
                c = C.pick_cards(picks[i], chars, 1, rng, drafters[i], cfg)[0]
                chars.remove(c)
                picks[i].append(c)
    else:  # mini_winchester: hands of 4, take 1, pass
        hands = [[chars.pop() for _ in range(4)] for _ in range(n)]
        for k in range(4):
            for i in range(n):
                hand = hands[(i - k) % n]
                if hand:
                    c = C.pick_cards(picks[i], hand, 1, rng, drafters[i], cfg)[0]
                    hand.remove(c)
                    picks[i].append(c)

    # ---- 3. gear winchester ----
    hs = LEVERS["gear_hand_size"]
    passes = (hs - 2) // 2          # 10 -> 4 passes (16 cards); 8 -> 3 (12 cards)
    gear = _gear_pool(rng, n, hs)
    for _ in range(2):
        hands = [[gear.pop() for _ in range(hs)] for _ in range(n)]
        for k in range(passes):
            for i in range(n):
                hand = hands[(i - k) % n]
                if len(hand) > 2:
                    take = C.pick_cards(picks[i], hand, 2, rng, drafters[i], cfg)
                    for c in take:
                        hand.remove(c)
                        picks[i].append(c)
        for h in hands:
            h.clear()               # last 2 of each hand discarded
    return picks


# ------------------------------------------------- 5. first-round turn order
def _initial_order(teams, cfg, rng):
    """run_engine rotates init once before round 0, so we pre-rotate:
    return [highest] + ascending[:-1]  =>  after rotation, highest is LAST."""
    idx = list(range(len(teams)))
    rng.shuffle(idx)                        # consume rng identically either way
    if not LEVERS["speed_first_order"]:
        return idx
    spd = {i: C.pooled(teams[i], cfg, False)[C.S] for i in idx}
    asc = sorted(idx, key=lambda i: (spd[i], teams[i].tiebreak))
    return [asc[-1]] + asc[:-1]


# ------------------------------------------------------ 6. hazard direct dmg
_ORIG_RESOLVE_ATTACK = C.resolve_attack


def _resolve_attack(team, target, cfg, track, teams=None):
    out = _ORIG_RESOLVE_ATTACK(team, target, cfg, track, teams=teams)
    dmg = LEVERS["hazard_direct_damage"]
    if dmg and target is not None and target.finished_round is None:
        if track[target.loc_idx].effect == "hazard":
            d = target.loc_idx - team.loc_idx
            reach = C.attack_reach(team, cfg)
            if (d == 0) or C.ranged_dir_ok(team, d, reach, cfg):
                C.deal_direct(target, dmg)
    return out


# --------------------------------------------------- patch installation
_ORIG_SNAKE = C.snake_draft
_ORIG_COMMIT = C._commit_v2
_ORIG_RUN_ENGINE = C.run_engine
_installed = False

# NOTE: the bare coercion line appears TWICE in _commit_v2 (the second inside
# the pacifist_pids branch, at deeper indent). Target the unique two-line form
# so we only patch the real action-repeat rule.
_COERCE_SRC = ('    if combat == progress and combat != "move":\n'
               '        combat = "defend" if combat != "defend" else "move"')
_COERCE_NEW = ('    if combat == progress and combat != "move" and not '
               '(combat == "breach" and LEVERS["allow_double_breach"]):\n'
               '        combat = "defend" if combat != "defend" else "move"')
_ORDER_SRC = "init = list(range(len(teams))); rng.shuffle(init)"
_ORDER_NEW = "init = _initial_order(teams, cfg, rng)"


def install():
    """Patch draft, double-breach coercion, first-round order, hazard damage.

    ORDERING NOTE: install() BEFORE special_harness.install(), because the
    harness also wraps _commit_v2 and captures whatever it finds at install
    time. v7 first -> harness wraps the v7 version -> both survive.
    """
    global _installed
    C.snake_draft = v7_draft
    C.resolve_attack = _resolve_attack

    ns = C.__dict__
    ns["LEVERS"] = LEVERS
    ns["_initial_order"] = _initial_order

    src = inspect.getsource(_ORIG_COMMIT)
    assert src.count(_COERCE_SRC) == 1, "action-coercion line not found (engine changed?)"
    exec(compile(src.replace(_COERCE_SRC, _COERCE_NEW), "<v7_commit>", "exec"), ns)

    src = inspect.getsource(_ORIG_RUN_ENGINE)
    assert src.count(_ORDER_SRC) == 1, "init-order line not found (engine changed?)"
    exec(compile(src.replace(_ORDER_SRC, _ORDER_NEW), "<v7_order>", "exec"), ns)

    _installed = True


def uninstall():
    global _installed
    C.snake_draft = _ORIG_SNAKE
    C.resolve_attack = _ORIG_RESOLVE_ATTACK
    C._commit_v2 = _ORIG_COMMIT
    C.run_engine = _ORIG_RUN_ENGINE
    for k in ("LEVERS", "_initial_order"):
        C.__dict__.pop(k, None)
    LEVERS.update(_DEFAULTS)
    _installed = False
