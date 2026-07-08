"""
Cybershot special-action-card TEST HARNESS  (Phase A scaffolding)
------------------------------------------------------------------
Additive, runtime-patch layer over cybershot_sim. Canonical engine is NOT edited.
Design invariant: with nothing enabled/forced, every patch is a pass-through, so
run_config(V5_CONFIG()) reproduces T11a bit-for-bit.

What it wires now (Advanced tier / buff-then-single-action):
  - SPECIAL_CARDS registry (Advanced fully specified; Ultimates = specs, resolvers pending)
  - deck injection (force a card into a team's deck for Phase-B isolation)
  - consumption hook: pre-effects (stat buff / heal N / draw N) + ultimate->exile routing
  - CARD_TYPES extension so the drafter/AI can match wants to special cards
Deferred (flagged, wired at their phase):
  - multi-action cards (Onslaught = 2 attacks, Zypher variant-B = move+brace)
  - Ultimate bespoke resolvers (teleport, global dmg, leader-knockback, auto-resolve counter)
  - draft_value / draftability (only needed Phase D/E; Phase B uses forced inclusion)
"""
import cybershot_sim as C
from cybershot_sim import L, M, S, V, W  # stat indices 0..4

# ------------------------------------------------------------------ registry
# want   = action tuple used for AI want-matching (mirrors CARD_TYPES)
# buff   = (stat_idx, amount) applied via add_temp on consume, or None
# heal   = HP healed on consume (pre-effect)
# draw   = cards drawn on consume (pre-effect)
# acts   = basic actions the card resolves as (len>1 => multi-action, deferred)
# complex= True if it needs bespoke handling not covered by the simple path
SPECIAL_CARDS = {
  # ---- ADVANCED (reusable; reshuffled) ----
  "ADV_defenddraw": dict(name="Defend-Draw",   tier="advanced", want=("defend","draw"), buff=None,     heal=0, draw=2, acts=["defend"], job="econ/tempo",       complex=False),
  "ADV_sapstrike":  dict(name="Sapping Strike", tier="advanced", want=("attack","draw"), buff=None,     heal=0, draw=2, acts=["attack"], job="econ/tempo",       complex=False),
  "ADV_soothe":     dict(name="Soothing Shield",tier="advanced", want=("defend","heal"), buff=None,     heal=2, draw=0, acts=["defend"], job="sustain",          complex=False),
  "ADV_zypher_a":   dict(name="Zypher (spd)",   tier="advanced", want=("defend",),       buff=(S,2),    heal=0, draw=0, acts=["defend"], job="speed-buff/brace",  complex=False),
  "ADV_zypher_b":   dict(name="Zypher (move)",  tier="advanced", want=("move","defend"), buff=None,     heal=0, draw=0, acts=["move","defend"], bonus=["move","defend"], noprimary=True, job="dual-action", complex=True),
  "ADV_onslaught":  dict(name="Onslaught",      tier="advanced", want=("attack",),       buff=None,     heal=0, draw=0, acts=["attack","attack"], bonus=["attack","attack"], noprimary=True, job="burst-dmg", complex=True),
  "ADV_rally":      dict(name="Rally",          tier="advanced", want=("heal","draw"),   buff=None,     heal=2, draw=2, acts=[],         bonus=[], noprimary=True, job="sustain/econ",     complex=True),
  "ADV_savage":     dict(name="Savage Assault", tier="advanced", want=("attack",),       buff=(L,2),    heal=0, draw=0, acts=["attack"], job="lethality-boost",  complex=False),
  "ADV_sprint":     dict(name="Sprint",         tier="advanced", want=("move",),         buff=(S,3),    heal=0, draw=0, acts=["move"],   job="speed-revive/pace", complex=False),
  "ADV_crash":      dict(name="Crash Override", tier="advanced", want=("breach",),       buff=(W,3),    heal=0, draw=0, acts=["breach"], job="willpower/breach", complex=False),
  "ADV_brainbuzz":  dict(name="Brain Buzz",     tier="advanced", want=("breach","draw"), buff=None,     heal=0, draw=3, acts=["breach"], job="econ+progress",    complex=False),
  "ADV_heavyguard": dict(name="Heavy Guard",    tier="advanced", want=("defend",),       buff=(L,2),    heal=0, draw=0, acts=["defend"], job="leth-on-brace",    complex=False),

  "ADV_recompile":  dict(name="Recompile",     tier="advanced", want=("move",),        buff=None, heal=0, draw=2, discard=1, acts=["move"], job="filter/econ", complex=False),
  "ADV_suppress":   dict(name="Suppressing Fire",tier="advanced", want=("attack",),      resolver=True, noprimary=True, job="control-attack"),
  "ADV_overclock":  dict(name="Overclock",      tier="advanced", want=("breach","draw"), resolver=True, noprimary=True, job="econ+progress"),
  "ULT_warpgate":   dict(name="Warp Gate",      tier="ult",      want=("move","breach"), effect="complete current traversal -> next loc", complex=True),
  "ULT_hijack":     dict(name="Hijack",         tier="ult",      want=("move",),         effect="teleport to leader loc + draw 2", complex=True),
  # ==== V6 SPECIAL TACTICS (reusable; ultimates cut) ====
  "ADV_zypher":     dict(name="Zypher Maneuver", tier="advanced", want=("move",),   buff=(M,2), heal=0, draw=0, acts=["move"],   job="mit-buff/move"),
  "ADV_bulwark":    dict(name="Bulwark Maneuver",tier="advanced", want=("attack",), buff=(M,2), heal=0, draw=0, acts=["attack"], job="mit-buff/attack"),
  "ADV_huntergambit":dict(name="Hunter's Gambit",tier="advanced", want=("attack",), resolver=True, noprimary=True, job="direct-dmg"),
  "ADV_hardreset2": dict(name="Hard Reset",     tier="advanced", want=("draw",),   resolver=True, noprimary=True, job="refresh"),
  "ADV_hamstring":  dict(name="Hamstring Strike",tier="advanced",want=("attack",), resolver=True, noprimary=True, job="control-attack"),
  "ADV_smoke2":     dict(name="Smokescreen Fog",tier="advanced", want=("defend",), noprimary=True, job="ranged-immunity"),
  "ADV_bolster2":   dict(name="Bolster",        tier="advanced", want=("defend","draw"), buff_all=2, draw=1, noprimary=True, job="broad-buff"),
  "ADV_phasejump":  dict(name="Phase Jump",     tier="advanced", want=("move",),   resolver=True, noprimary=True, job="teleport+selfdmg"),
  "ADV_healrain":   dict(name="Healing Rain",   tier="advanced", want=("heal",),   heal_each=1, noprimary=True, job="team-heal"),
  "ADV_crash2":     dict(name="Crash Override 2",tier="advanced",want=("breach","draw"), resolver=True, noprimary=True, job="breach-denial"),
  # ---- ULTIMATES (single-use; exile after play). Resolvers pending. ----
  "ULT_hkdart":     dict(name="Hunter Killer Dart", tier="ult", want=("attack",), effect="4 direct dmg (bypass Mit), team within 1 loc", complex=True, pending=True),
  "ULT_undermine":  dict(name="Undermine",          tier="ult", want=("attack",), effect="reset enemy traversal in loc; -2 S/-2 W (floor 1)", complex=True, pending=True),
  "ULT_hardreset":  dict(name="Hard Reset",         tier="ult", want=("draw",),   effect="discard hand, draw 5, heal each glad 1", complex=True, pending=True),
  "ULT_bolster":    dict(name="Bolster",            tier="ult", want=("defend",), effect="+3 all stats EOR; draw 2", complex=True, pending=True),
  "ULT_cleanse":    dict(name="Cleansing Rain",     tier="ult", want=("heal",),   effect="heal all glads +4", complex=True, pending=True),
  "ULT_smoke":      dict(name="Smokescreen Fog",    tier="ult", want=("defend",), effect="prevent all attack dmg in loc for round", complex=True, pending=True),
  "ULT_phase":      dict(name="Phase Shift",        tier="ult", want=("move",),   effect="teleport to any revealed location", complex=True, pending=True),
  "ULT_barrier":    dict(name="Over the Barrier",   tier="ult", want=("breach",), effect="auto-resolve traversal/breach counter in loc", complex=True, pending=True),
  "ULT_blueshell":  dict(name="BlueShell Protocol", tier="ult", want=("move",),   effect="leader back 1 location; reset that loc counters", complex=True, pending=True),
  "ULT_firebomb":   dict(name="Firebomb",           tier="ult", want=("attack",), effect="3 direct dmg to all enemies in loc", complex=True, pending=True),
  "ULT_dreadsnap":  dict(name="Dreadsnap",          tier="ult", want=("attack",), effect="1 dmg to ALL gladiators in game", complex=True, pending=True),
  "ULT_deaden":     dict(name="Deadening Strike",   tier="ult", want=("attack",), effect="+3 L/atk; on hit -3 S/-3 W EOR", complex=True, pending=True),
  "ULT_berserk":    dict(name="Berserker's Call",   tier="ult", want=("attack",), effect="+6 L/atk; self 3 direct dmg", complex=True, pending=True),
}


# mark all ultimates noprimary (their whole effect is the resolver) and give exile pile
for _c,_sp in SPECIAL_CARDS.items():
    if _sp.get("tier")=="ult":
        _sp["noprimary"]=True

# ------------------------------------------------------------------ state
class _HS:
    enabled = set()      # codes present in draft pool / deck (Phase D/E)
    force = {}           # pid -> [codes] forced into that team's deck (Phase B). 'all' key = every team.
    rng = None           # captured each round for pre-effect draws
    plays = {}           # code -> times actually played (drafted-but-dead detector)
    teams = None; track = None; cfg = None   # stashed each turn for ult triggers
    pool_enabled = set()   # codes eligible for the draft pool (Phase D/E)
    pool_copies = 1        # copies of each enabled special added to the pool
    max_specials = 2       # soft cap: specials a team will draft
    track_locs = False     # accumulate per-location round occupancy
    loc_rounds = {}; loc_visits = {}
    vault_override = None   # override FinalVault breach counter
    rule1 = False          # brace lost on move
    rule2 = False          # adjacent attacks -2 Lethality (Ranged negates)
HS = _HS()

def reset():
    HS.enabled = set(); HS.force = {}; HS.plays = {}; HS.pool_enabled = set()
    HS.loc_rounds = {}; HS.loc_visits = {}

# ------------------------------------------------------------------ patches
_orig_take_card = C.take_card
_orig_build_team = C.build_team
_orig_draw_hand = C.draw_hand
_orig_add_temp = C.add_temp
_orig_apply_hack = C.apply_hack
_orig_commit = C._commit_v2
_orig_alloc = C.allocate_damage
_orig_resolve_attack = C.resolve_attack
_orig_resolve_move = C.resolve_move
_orig_make_pool = C.make_pool
_orig_build_track = C.build_track
_orig_card_value = C.card_value

def _add_temp_uncapped(team, stat, amt, source="?"):
    """CANONICAL RULE CHANGE (per George): flag over-+3 temp bonuses, don't block them.
    Alarm still fires by source when cumulative want exceeds ABILITY_CAP; no clipping."""
    cur = team.temp_mods[stat]
    want = cur + amt
    if want > C.ABILITY_CAP:
        C._CAPALARM[source] = C._CAPALARM.get(source, 0) + 1
    team.temp_mods[stat] = want

def _consume(team, card, cfg):
    """Route a consumed card: apply pre-effects / stash bonus / fire ult resolver; exile ults else discard."""
    spec = SPECIAL_CARDS.get(card)
    if spec is None:
        team.discard.append(card); return
    HS.plays[card] = HS.plays.get(card, 0) + 1
    if not hasattr(team, "_special_bonus"): team._special_bonus = []
    is_ult = spec.get("tier") == "ult"
    if card == "ULT_smoke":
        team._smoke = True
    elif card == "ADV_smoke2":
        team._smoke_ranged = True
    elif is_ult or spec.get("resolver"):
        team._special_bonus.append(("__ULT__", card))   # custom resolver, post-stack
    else:
        b = spec.get("buff")
        if b: C.add_temp(team, b[0], b[1], card)
        if spec.get("buff_all"):
            for _i in range(5): C.add_temp(team, _i, spec["buff_all"], card)
        if spec.get("heal"):  C.heal_team(team, spec["heal"], cfg)
        if spec.get("heal_each"): _heal_each(team, spec["heal_each"])
        if spec.get("discard"):
            for _ in range(spec["discard"]):
                if team.hand: team.discard.append(team.hand.pop())
        if spec.get("draw") and HS.rng is not None: C._draw_n(team, cfg, HS.rng, spec["draw"])
        bonus = spec.get("bonus")
        if bonus: team._special_bonus.extend(bonus)
    if is_ult:
        if not hasattr(team, "exile"): team.exile = []
        team.exile.append(card)
    else:
        team.discard.append(card)

def _take_card(team, want, cfg=None):
    CT = C.CARD_TYPES
    if want == "breach" and cfg is not None and cfg.burn_to_hack and team.hand:
        card = next((c for c in team.hand if "breach" in CT[c]), team.hand[0])
        team.hand.remove(card); _consume(team, card, cfg)
        return None if SPECIAL_CARDS.get(card,{}).get("noprimary") else "breach"
    card = next((c for c in team.hand if want in CT[c] and _ult_ready(c, team)), None)
    if card is None and want in ("attack","defend") and cfg is not None and cfg.enable_char_abilities and "flex" in C.active_quirks(team):
        other = "defend" if want == "attack" else "attack"
        card = next((c for c in team.hand if other in CT[c]), None)
        if card is not None:
            team.hand.remove(card); _consume(team, card, cfg)
            return None if SPECIAL_CARDS.get(card,{}).get("noprimary") else want
    if card is None and team.hand: card = team.hand[0]
    if card is None: return None
    team.hand.remove(card); _consume(team, card, cfg)
    if SPECIAL_CARDS.get(card,{}).get("noprimary"): return None
    opts = CT[card]
    if want in opts: return want
    return next((o for o in ("breach","move","defend","attack","heal") if o in opts), opts[0])

def _build_team(pid, drafted, cfg, rng):
    team = _orig_build_team(pid, drafted, cfg, rng)
    drafted_specials = [c["name"] for c in drafted if isinstance(c, dict) and c.get("kind")=="special"]
    forced = list(HS.force.get(pid, [])) + list(HS.force.get("all", []))
    add = drafted_specials + forced
    if add:
        for code in add: team.deck.append(code)
        team._drafted_specials = drafted_specials
        rng.shuffle(team.deck)
    return team

def _draw_hand(team, cfg, rng):
    HS.rng = rng                      # capture rng for pre-effect draws
    return _orig_draw_hand(team, cfg, rng)

def _apply_hack(t, teams, cfg, track):
    """Resolve stashed multi-action bonus board effects post-stack (bypasses 2-action cap)."""
    if HS.track_locs:
        Lx = t.loc_idx
        HS.loc_rounds[Lx] = HS.loc_rounds.get(Lx, 0) + 1
        if getattr(t, "_ploc", -2) != Lx:
            HS.loc_visits[Lx] = HS.loc_visits.get(Lx, 0) + 1; t._ploc = Lx
    if getattr(t, "_smoke", False): t._smoke = False   # smoke lasts one round
    if getattr(t, "_smoke_ranged", False): t._smoke_ranged = False
    bonus = getattr(t, "_special_bonus", None)
    if bonus:
        for atype in bonus:
            if isinstance(atype, tuple) and atype[0] == "__ULT__":
                fn = ULT_RESOLVERS.get(atype[1])
                if fn: fn(t, teams, cfg, track)
                continue
            if atype == "attack":
                tgt = C.best_attack_target(t, teams, cfg, track)
                if tgt is not None:
                    tgt.times_attacked += 1
                    C.resolve_attack(t, tgt, cfg, track, teams=teams)
            elif atype == "move":
                C.resolve_move(t, teams, cfg, track)
            elif atype == "breach":
                t.breached_this_turn = True; C.resolve_breach(t, teams, cfg, track, HS.rng)
            elif atype == "defend":
                t.braced = True; t.braced_this_turn = True
            elif atype == "heal":
                C.heal_team(t, 1, cfg)
        t._special_bonus = []
    return _orig_apply_hack(t, teams, cfg, track)


# ---- draft_value derived from measured Phase-B win-lift (E-calibration) ----
_LIFT = {
 "ADV_onslaught":0.095,"ADV_sapstrike":0.093,"ADV_savage":0.088,"ADV_brainbuzz":0.073,
 "ADV_rally":0.050,"ADV_defenddraw":0.047,"ADV_crash":-0.001,"ADV_zypher_b":-0.003,
 "ADV_sprint":-0.009,"ADV_soothe":-0.009,"ADV_zypher_a":-0.012,"ADV_heavyguard":-0.022,
 "ULT_deaden":0.028,"ULT_hardreset":0.019,"ULT_berserk":0.017,"ULT_smoke":0.014,
 "ULT_hkdart":0.007,"ULT_phase":0.005,"ULT_firebomb":0.004,"ULT_bolster":0.001,
 "ULT_barrier":-0.002,"ULT_dreadsnap":-0.003,"ULT_cleanse":-0.010,"ULT_undermine":-0.013,
 "ULT_blueshell":-0.027,
 "ADV_recompile":0.051,"ADV_suppress":-0.006,"ADV_overclock":0.034,
 "ULT_warpgate":-0.019,"ULT_hijack":0.009,
}
DVAL = {c: round(max(2.0, 6.0 + 110.0*L_), 1) for c,L_ in _LIFT.items()}
# V6 measured lifts (9-loc Phase B) -> refresh draft values
_V6_LIFT = {
 "ADV_sapstrike":0.103,"ADV_crash2":0.079,"ADV_savage":0.073,"ADV_hardreset2":0.071,
 "ADV_brainbuzz":0.058,"ADV_bulwark":0.052,"ADV_hamstring":0.044,"ADV_rally":0.043,
 "ADV_defenddraw":0.036,"ADV_recompile":0.023,"ADV_bolster2":0.008,"ADV_overclock":0.006,
 "ADV_huntergambit":-0.001,"ADV_zypher":-0.006,"ADV_smoke2":-0.018,"ADV_healrain":-0.024,
 "ADV_phasejump":-0.211,
}
_LIFT.update(_V6_LIFT)
DVAL.update({c: round(max(2.0, 6.0+110.0*L_),1) for c,L_ in _V6_LIFT.items()})


# ============================ ULTIMATE LAYER ============================
def _heal_each(team, n, revive=False):
    for g in team.glads:
        if g.downed and not revive: continue
        g.hp = min(g.maxhp, g.hp + n)
        if revive and g.hp > 0: g.downed = False

def _enemies(team, teams):
    return [o for o in teams if o is not team and o.finished_round is None]
def _frontier(teams):
    a=[o.loc_idx for o in teams if o.finished_round is None]; return max(a) if a else 0

# ---- triggers: return True if the bot should play this ult now (else it holds it) ----
def _trg_blueshell(t,teams,cfg,track):
    L_=C.race_leader(teams); return L_ is not None and L_ is not t and L_.loc_idx>t.loc_idx
def _trg_phase(t,teams,cfg,track):   return t.loc_idx < _frontier(teams)
def _trg_barrier(t,teams,cfg,track): return t.breach_remaining>0 or t.trav_remaining>3
def _trg_incol(t,teams,cfg,track):   return any(o.loc_idx==t.loc_idx for o in _enemies(t,teams))
def _trg_within1(t,teams,cfg,track): return any(abs(o.loc_idx-t.loc_idx)<=1 for o in _enemies(t,teams))
def _trg_dread(t,teams,cfg,track):   return any(g.hp<=1 and not g.downed for o in _enemies(t,teams) for g in o.glads)
def _trg_cleanse(t,teams,cfg,track): return any(g.hp<g.maxhp or g.downed for g in t.glads)
def _trg_smoke(t,teams,cfg,track):   return any(abs(o.loc_idx-t.loc_idx)<=1 for o in _enemies(t,teams))
def _trg_atk(t,teams,cfg,track):     return C.best_attack_target(t,teams,cfg,track) is not None
def _trg_warpgate(t,teams,cfg,track): return t.trav_remaining>0 or t.trav_i<len(track[t.loc_idx].trav)
ULT_TRIGGERS = {
  "ULT_blueshell":_trg_blueshell, "ULT_phase":_trg_phase, "ULT_barrier":_trg_barrier,
  "ULT_firebomb":_trg_incol, "ULT_undermine":_trg_incol, "ULT_hkdart":_trg_within1,
  "ULT_dreadsnap":_trg_dread, "ULT_cleanse":_trg_cleanse, "ULT_smoke":_trg_smoke,
  "ULT_bolster":_trg_atk, "ULT_deaden":_trg_atk, "ULT_berserk":_trg_atk,
  "ULT_warpgate":_trg_warpgate, "ULT_hijack":_trg_phase,
  # ULT_hardreset: no trigger => always ready
}
def _ult_ready(card, team):
    sp=SPECIAL_CARDS.get(card)
    if sp is None or sp.get("tier")!="ult": return True
    trg=ULT_TRIGGERS.get(card)
    if trg is None: return True
    if HS.teams is None: return True
    try: return bool(trg(team, HS.teams, HS.cfg, HS.track))
    except Exception: return True

# ---- resolvers (fired post-stack in _apply_hack, except smoke which is consume-time) ----
def _r_blueshell(t,teams,cfg,track):
    L_=C.race_leader(teams)
    if L_ is not None and L_ is not t and L_.loc_idx>0:
        L_.loc_idx=max(0,L_.loc_idx-1); loc=track[L_.loc_idx]
        L_.trav_i=0; L_.trav_remaining=loc.trav[0] if loc.trav else 0; L_.breach_remaining=loc.breach
def _r_phase(t,teams,cfg,track):
    fr=_frontier(teams)
    if t.loc_idx<fr:
        t.loc_idx=fr; loc=track[fr]
        t.trav_i=0; t.trav_remaining=loc.trav[0] if loc.trav else 0; t.breach_remaining=loc.breach
def _r_barrier(t,teams,cfg,track):
    loc=track[t.loc_idx]
    if t.breach_remaining>0:
        t.breach_remaining-=1
    elif t.trav_remaining>0:
        t.trav_remaining-=1
        if t.trav_remaining<=0:
            t.trav_i+=1
            t.trav_remaining=loc.trav[t.trav_i] if t.trav_i<len(loc.trav) else 0
    if t.trav_i>=len(loc.trav) and t.breach_remaining<=0:
        C.advance(t,teams,cfg,track)
def _r_dreadsnap(t,teams,cfg,track):
    for o in teams:
        for g in o.glads: C.deal_to_gladiator(g,1)
def _r_hkdart(t,teams,cfg,track):
    tg=[o for o in _enemies(t,teams) if abs(o.loc_idx-t.loc_idx)<=1 and any(not g.downed for g in o.glads)]
    if tg: C.deal_direct(max(tg,key=lambda o:o.loc_idx),4)
def _r_firebomb(t,teams,cfg,track):
    for o in _enemies(t,teams):
        if o.loc_idx==t.loc_idx: C.deal_direct(o,3)
def _r_undermine(t,teams,cfg,track):
    tg=[o for o in _enemies(t,teams) if o.loc_idx==t.loc_idx]
    if tg:
        o=max(tg,key=lambda x:(x.loc_idx,-x.trav_remaining)); loc=track[o.loc_idx]
        o.trav_remaining=loc.trav[o.trav_i] if o.trav_i<len(loc.trav) else (loc.trav[0] if loc.trav else 0)
        C.add_temp(o,S,-2,"ULT_undermine"); C.add_temp(o,W,-2,"ULT_undermine")
def _r_hardreset(t,teams,cfg,track):
    t.discard.extend(t.hand); t.hand=[]
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,5)
    _heal_each(t,1)
def _r_bolster(t,teams,cfg,track):
    for i in range(5): C.add_temp(t,i,3,"ULT_bolster")
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,2)
def _r_cleanse(t,teams,cfg,track): _heal_each(t,4,revive=True)
def _r_deaden(t,teams,cfg,track):
    C.add_temp(t,L,3,"ULT_deaden"); tg=C.best_attack_target(t,teams,cfg,track)
    if tg is not None:
        tg.times_attacked+=1; C.resolve_attack(t,tg,cfg,track,teams=teams)
        C.add_temp(tg,S,-3,"ULT_deaden"); C.add_temp(tg,W,-3,"ULT_deaden")
def _r_berserk(t,teams,cfg,track):
    C.add_temp(t,L,6,"ULT_berserk"); tg=C.best_attack_target(t,teams,cfg,track)
    if tg is not None:
        tg.times_attacked+=1; C.resolve_attack(t,tg,cfg,track,teams=teams)
    C.deal_direct(t,3)
def _r_suppress(t,teams,cfg,track):
    tg=C.best_attack_target(t,teams,cfg,track)
    if tg is not None:
        C.deal_direct(tg,1); C.add_temp(tg,S,-2,"ADV_suppress")
def _r_overclock(t,teams,cfg,track):
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,1)
    before=t.breach_remaining
    C.resolve_breach(t,teams,cfg,track,HS.rng)
    if before>0 and t.breach_remaining<=0:
        C.resolve_move(t,teams,cfg,track)
def _r_warpgate(t,teams,cfg,track):
    loc=track[t.loc_idx]
    t.trav_i=len(loc.trav); t.trav_remaining=0
    if t.breach_remaining<=0: C.advance(t,teams,cfg,track)
def _r_hijack(t,teams,cfg,track):
    _r_phase(t,teams,cfg,track)
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,2)
def _r_huntergambit(t,teams,cfg,track):
    tg=[o for o in _enemies(t,teams) if abs(o.loc_idx-t.loc_idx)<=1 and any(not g.downed for g in o.glads)]
    if tg: C.deal_direct(max(tg,key=lambda o:o.loc_idx),2)
def _r_hardreset2(t,teams,cfg,track):
    t.discard.extend(t.hand); t.hand=[]
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,5)
    _heal_each(t,1)
def _r_hamstring(t,teams,cfg,track):
    C.add_temp(t,L,1,"ADV_hamstring"); tg=C.best_attack_target(t,teams,cfg,track)
    if tg is not None:
        b=sum(g.dmg_total for g in tg.glads); tg.times_attacked+=1
        C.resolve_attack(t,tg,cfg,track,teams=teams)
        if sum(g.dmg_total for g in tg.glads)>b: C.add_temp(tg,S,-2,"ADV_hamstring")
def _r_phasejump(t,teams,cfg,track):
    # EDITED: "Move to any revealed location; your team takes 4 direct damage" (team-level, not per-glad)
    _r_phase(t,teams,cfg,track)
    C.deal_direct(t,4)
def _r_crash2(t,teams,cfg,track):
    # EDITED: "Draw 1, then Breach; if you resolve a breach counter, reset all enemy breach counters here"
    if HS.rng is not None: C._draw_n(t,cfg,HS.rng,1)
    before=t.breach_remaining
    C.resolve_breach(t,teams,cfg,track,HS.rng)
    if before>0 and t.breach_remaining<=0:
        for o in _enemies(t,teams):
            if o.loc_idx==t.loc_idx: o.breach_remaining=0

ULT_RESOLVERS = {
  "ADV_huntergambit":_r_huntergambit, "ADV_hardreset2":_r_hardreset2, "ADV_hamstring":_r_hamstring,
  "ADV_phasejump":_r_phasejump, "ADV_crash2":_r_crash2,
  "ADV_suppress":_r_suppress, "ADV_overclock":_r_overclock, "ULT_warpgate":_r_warpgate, "ULT_hijack":_r_hijack,
  "ULT_blueshell":_r_blueshell, "ULT_phase":_r_phase, "ULT_barrier":_r_barrier,
  "ULT_dreadsnap":_r_dreadsnap, "ULT_hkdart":_r_hkdart, "ULT_firebomb":_r_firebomb,
  "ULT_undermine":_r_undermine, "ULT_hardreset":_r_hardreset, "ULT_bolster":_r_bolster,
  "ULT_cleanse":_r_cleanse, "ULT_deaden":_r_deaden, "ULT_berserk":_r_berserk,
  # ULT_smoke handled at consume-time via team._smoke + allocate immunity
}

def _commit_v2(*args, **kwargs):
    # real signature: (team,progress,combat,ctgt,tgt,cfg,at_gate,threat,teams,track,dt,deny)
    if len(args) > 9:
        HS.cfg = args[5]; HS.teams = args[8]; HS.track = args[9]
    return _orig_commit(*args, **kwargs)

def _resolve_attack(team, target, cfg, track, teams=None):
    # Smokescreen (card effect): ranged damage fully prevented this round.
    # (Rule 2 adjacent-Lethality penalty is now handled by the engine via cfg.adjacent_leth_penalty.)
    if getattr(target, "_smoke_ranged", False) and (target.loc_idx - team.loc_idx) != 0:
        return 0
    return _orig_resolve_attack(team, target, cfg, track, teams=teams)

def _resolve_move(team, teams, cfg, track):
    # Rule 1: a move undoes an existing brace (timing matters)
    if HS.rule1 and getattr(team, "braced", False):
        team.braced = False
    return _orig_resolve_move(team, teams, cfg, track)

def _allocate_damage(target, dmg):
    if getattr(target, "_smoke", False): return
    return _orig_alloc(target, dmg)


def _build_track(*args, **kwargs):
    # forward-compatible with the V6 engine signature (vault_breach/layout kwargs now handled by the engine)
    track = _orig_build_track(*args, **kwargs)
    if HS.vault_override is not None:   # legacy override still honored if explicitly set
        for loc in track:
            if loc.effect == "finalvault": loc.breach = HS.vault_override
    return track

def _make_pool(rng):
    pool = _orig_make_pool(rng)
    if HS.pool_enabled and HS.pool_copies > 0:
        for _ in range(HS.pool_copies):
            for code in HS.pool_enabled:
                pool.append({"kind":"special","name":code})
        rng.shuffle(pool)
    return pool

def _card_value(have, card, cfg):
    if card.get("kind") == "special":
        n_spec = sum(1 for c in have if c.get("kind")=="special")
        if n_spec >= HS.max_specials: return 2.0     # soft cap
        return DVAL.get(card["name"], 4.0)
    return _orig_card_value(have, card, cfg)


def install():
    # extend CARD_TYPES with special want-tuples (additive; harmless if unused)
    for code, spec in SPECIAL_CARDS.items():
        C.CARD_TYPES[code] = spec["want"]
    C.take_card = _take_card
    C.build_team = _build_team
    C.draw_hand = _draw_hand
    C.apply_hack = _apply_hack   # NOTE: cap removal + Rule 1/2 now handled by the V6 engine config
    C._commit_v2 = _commit_v2
    C.allocate_damage = _allocate_damage
    C.resolve_attack = _resolve_attack   # kept only for Smokescreen (ranged-immunity card effect)
    C.make_pool = _make_pool
    C.card_value = _card_value
    C.build_track = _build_track

def uninstall():
    C.take_card = _orig_take_card
    C.build_team = _orig_build_team
    C.draw_hand = _orig_draw_hand
    C.apply_hack = _orig_apply_hack
    C._commit_v2 = _orig_commit
    C.allocate_damage = _orig_alloc
    C.resolve_attack = _orig_resolve_attack
    C.make_pool = _orig_make_pool
    C.card_value = _orig_card_value
    C.build_track = _orig_build_track
    for code in SPECIAL_CARDS:
        C.CARD_TYPES.pop(code, None)

V6_SET = ["ADV_defenddraw","ADV_sapstrike","ADV_rally","ADV_savage","ADV_brainbuzz","ADV_recompile",
          "ADV_zypher","ADV_bulwark","ADV_huntergambit","ADV_hardreset2","ADV_hamstring","ADV_smoke2",
          "ADV_bolster2","ADV_phasejump","ADV_healrain","ADV_overclock","ADV_crash2"]
