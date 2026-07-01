"""
CYBERSHOT GLADIATORS - Balance Simulation (V2 design test)
===========================================================
Measures STRUCTURAL balance under reasonable (greedy) play.
Both sides play identical greedy heuristics, so outcome SPREAD reflects
card/draft variance under sensible play => the "decided at the draft" question.
Approximations marked #APPROX. Stat vector: [L,M,S,V,W].
Pooled for actions: L,M,S,W.  Per-gladiator only: V (=HP).
"""
import random, statistics, math
from dataclasses import dataclass, field
import numpy as np
from scipy.stats import spearmanr

L, M, S, V, W = 0, 1, 2, 3, 4
STAT_NAMES = ["L","M","S","V","W"]
STAT_WEIGHTS = [0.90, 1.68, 0.38, 0.73, 1.01]  # L, M, S, V, W -- empirically calibrated (floor 0.22, sum 4.70)
_YOMI = {"standoff": 0, "multi": 0}
_COMBAT = {"gate_dec": 0, "gate_atk": 0, "gate_brace": 0, "attacks": 0, "braces": 0, "sprints": 0}
_REGROUP = {"turns": 0, "regroups": 0, "forced": 0, "voluntary": 0}
_CAPALARM = {}

ABILITY_CAP = 3

def add_temp(team, stat, amt, source="?"):
    cur = team.temp_mods[stat]
    want = cur + amt
    if want > ABILITY_CAP:
        _CAPALARM[source] = _CAPALARM.get(source, 0) + 1
        want = ABILITY_CAP
    team.temp_mods[stat] = want
_TENSION = {"gn": [], "gf": []}

CHARACTERS = {
    "Russ":     ([3,1,0,2,0], "intimidate"),
    "Lys":      ([2,0,3,1,0], "momentum"),
    "Gideon":   ([2,2,0,3,0], "go_beyond"),
    "Barhg":    ([1,0,1,1,3], "eager"),
    "Soren":    ([3,0,1,1,1], "sniper"),
    "BigSam":   ([0,2,0,5,0], "endure"),
    "Visper":   ([2,1,3,1,0], "ghoststep"),
    "Ayjax":    ([2,1,0,4,0], "brawler"),
    "Hera":     ([0,2,1,2,2], "healtouch"),
    "Asura":    ([1,1,1,2,2], "tactician"),
    "Roach":    ([0,2,0,2,3], "comphacker"),
    "Loacrest": ([2,2,1,2,0], "riposte"),
    "Harmonex": ([2,2,0,2,1], "flex"),
    "Jayred":   ([2,1,2,1,1], "night_thief"),
    "Khan":     ([2,1,1,2,1], "live_off_land"),
    "Alyren":   ([2,0,1,2,2], "heal_exit"),
    "Scrap":    ([1,1,1,1,1], "master_none"),
}
LOADOUTS = {
    "Wirerunner":      ([L,S], "ld_move_leth",   None),
    "Cyberhawk":       ([L,S], "ld_pos_leth",    "ranged"),
    "ConduitChampion": ([L,M], "ld_stance",      "melee"),
    "VoltBerserker":   ([L,V], "ld_berserk",     "melee"),
    "SurgeBomber":     ([L,W], "ld_aoe",         "ranged"),
    "SurgeDancer":     ([M,S], "ld_move_mit",    None),
    "Bastion":         ([M,V], "ld_bastion",     None),
    "ShieldCannon":    ([M,V], "ld_shieldcannon",None),
    "Flagelator":      ([L,V], "ld_flagelator",  "melee"),
    "Firewall":        ([M,W], "breach_jam",     None),
    "Salve":           ([V,W], "ld_salve",       None),
    "Hexer":           ([S,W], "ld_hexer",       None),
    "Jester":          ([L,W], "ld_jester",      None),
    "Artifician":      ([M,W], "draw1",          None),
    "Wellspring":      ([V,W], "ld_wellspring",  None),
    "Psionic":         ([L,W], "ld_psionic",     None),
    "Tactimancer":     ([M,W], "ld_tactimancer", None),
}
EQUIPMENT = {
    "BigHammer":       ([ 2,-1,0,0,0], None),
    "OverladenCuirass":([ -1,2,0,0,0], None),
    "VoltScope":       ([ 1,0, 0,0,0], "ranged_range"),
    "MagplateCowl":    ([ 0,2, 0,0,0], "eq_finalvault"),
    "PhaseSyncBand":   ([ 0,0, 1,0,0], "eq_phase"),
    "SerratedVambrace":([ 1,0, 0,0,0], "eq_serrated"),
    "TwinCoreBlades":  ([ 3,-1,0,0,-1], "melee"),
    "KineticGreaves":  ([ 0,0, 2,0,0], "idle_strain"),
    "KineticLattice":  ([ 0,2, 0,0,0], "eq_kinetic"),
    "SurefireBuckler": ([ 0,3, 0,0,0], "guard_strain"),
    "SynapticOC":      ([ 0,0, 0,0,2], "breach_strain"),
    "ArkanShard":      ([ 1,0, 1,0,1], "no_heal"),
    "BackCapacitor":   ([ 0,1, 0,0,1], "eq_backcap"),
    "BalmOfGilead":    ([ 0,0, 0,0,0], "heal_boost"),
    "RecoilHarness":   ([ 0,0, 0,0,0], "eq_recoil"),
    "StaticCloak":     ([ 0,0, 0,0,0], "eq_cloak"),
    "RedlineArray":    ([ 0,0,-1,0,0], "eq_redline"),
    "GPS":             ([ 0,0, 0,0,0], "eq_gps"),
    "Caltraps":        ([ 0,0, 0,0,0], "eq_caltraps"),
    "MagneticGrapple": ([ 0,0, 0,0,0], "eq_grapple"),   # +2 S if not Leader
    "TheftProtocol":   ([ 0,0, 0,0,0], "eq_theft"),     # +3 W if not Leader, -1 W if Leader
    "HunterKillerScope":([ 0,0,0,0,0], "eq_hkscope"),   # +2 L when attacking the Leader
    "JammerProtocol":  ([ 0,0, 0,0,1], "eq_jammer"),    # +1 W; if not Leader, Leader -1 W
    "KineticSapper":   ([ 0,0, 1,0,0], "eq_sapper"),    # +1 S; if not Leader, Leader -1 S
    "SlipstreamDrafter":([ 0,0,0,0,0], "eq_slipdraft"),  # +1 S per location Leader is ahead of you
    "TariffField":     ([ 0,0, 1,0,1], "eq_tariff"),     # +1 S,+1 W; Leader's first-entry penalty +2
    "VaultSiphon":     ([ 0,0, 0,0,1], "eq_siphon"),     # +1 W; when Leader breaches, you gain +1 breach
    "UnderdogProtocol":([ 0,0, 0,0,0], "eq_underdog"),   # +3 to your lowest stat while in last place
}
CARD_TYPES = {
    "MA": ("move","attack"), "MB": ("move","breach"), "BA": ("breach","attack"),
    "H":  ("heal","move"), "MD": ("move","defend"), "BD": ("breach","defend"),
    "AD": ("attack","defend"),
    "sM": ("move",), "sA": ("attack",), "sB": ("breach",), "sD": ("defend",), "sH": ("heal",),
    "HD": ("heal","defend"), "DR": ("defend","draw"), "RH": ("draw","heal"),
}

@dataclass
class Location:
    name: str; trav: list; smod: int = 0; breach: int = 0; effect: str = ""

def build_track(vault_scale, gate_counter=14, gates=(3, 6)):
    g = int(round(gate_counter * vault_scale))
    locs = [
        Location("StartingGate",  [3],   0, 0, "safe"),
        Location("TwistedForest", [5,4],-1, 0, "rangeguard"),
        Location("OpenPlains",    [10], +1, 0, "rangeboost"),
        Location("Chokepoint3",   [3],   0, 0, "rangeboost"),
        Location("JaggedGroves",  [4,4],-2, 0, "meleeboost"),
        Location("RadiantOasis",  [5],   0, 0, "heal"),
        Location("Chokepoint6",   [3],   0, 0, "meleeboost"),
        Location("VolatileTrench",[7],  -1, 0, "hazard"),
        Location("FinalVault",    [3],   0, int(round(17*vault_scale)), "finalvault"),
    ]
    for gi in gates:
        locs[gi].breach = g; locs[gi].effect = "gate"; locs[gi].trav = [3]
    return locs
N_LOC = 9
HACK_EFFECTS = ("gate", "vault", "finalvault")

@dataclass
class Config:
    n_players: int = 4
    damage_cap: int = 3
    attack_floor: int = 2
    l_bonus_cap: int = 99
    down_factor: float = 0.5
    down_speed_factor: float = 0.5
    down_drag: float = 0.0
    down_team_move_factor: float = 1.0   # <1.0 = team moves at this fraction of Speed while ANY gladiator is down
    down_round_mode: str = "pool"        # "pool" | "ceil" | "floor" -- rounding of a downed gladiator's stat contribution
    down_stagger: float = 0.0            # traversal added to a team when one of its gladiators is downed by combat
    speed_breach_frac: float = 0.0       # fraction of team Speed added to breach progress (gives Speed a job at gates/vault)
    trailblazer_drag: float = 0.0
    slipstream_bonus: float = 0.0
    easy_revive: bool = False
    draft_type: str = "winchester"
    ranged_forward_only: bool = True
    leader_backward_ranged: bool = False   # if True, the Leader (only) may also fire backward at pursuers
    base_reach: int = 1
    focus_leader: bool = False
    catchup_aggro: float = 0.7
    combat_div: int = 1
    free_attack_per_turn: int = 0
    slipstream_graduated: bool = False
    gate_counter: int = 14
    hack_disrupt: str = "freeze"
    pushback_amount: int = 3
    gate_attack_prob: float = 0.6
    single_gate: bool = False
    extract_needed: int = 0
    vault_extract_counter: int = 0
    gemheart_speed_penalty: int = 2
    extract_mode: str = "survival"
    extract_disrupt: str = "freeze"
    measure_yomi: bool = False
    new_combat: bool = False
    uncapped: bool = False
    allow_sprint: bool = True
    brace_threat_prob: float = 0.55
    brace_min_threat: int = 3
    pacifist_pids: tuple = ()
    measure_tension: bool = False
    rubberband: bool = False
    vault_scale: float = 2.2
    loadout_bonus: int = 2
    hand_size: int = 5
    draw_per_turn: int = 2
    actions_per_turn: int = 2
    regroup: bool = False
    regroup_yield: int = 1
    start_hand: int = 4
    single_basics: bool = False
    deck_sM: int = 3; deck_sA: int = 2; deck_sB: int = 2; deck_sD: int = 2; deck_sH: int = 1
    draw_card_amount: int = 2
    econ_deck: bool = False
    deck_MA2: int = 2; deck_MB2: int = 2; deck_BA2: int = 2
    deck_HD: int = 2; deck_DR: int = 2; deck_RH: int = 2
    speed_draw_hook: bool = False
    speed_draw_threshold: int = 4
    catchup_draw: int = 0
    leader_draw_pen: int = 0
    first_entry_penalty: int = 0
    blue_shell_prob: float = 0.0
    blue_shell_knockback: int = 0
    blue_shell_gap: int = 2
    enable_char_abilities: bool = False
    enable_equip_abilities: bool = False
    enable_loadout_abilities: bool = False
    disabled_effects: set = field(default_factory=set)
    soften_drawbacks: bool = False
    burn_to_hack: bool = False
    hybrid_progress_deck: bool = False
    deck_MA: int = 6; deck_MB: int = 3; deck_BA: int = 3; deck_H: int = 2
    deck_MD: int = 3; deck_BD: int = 2; deck_AD: int = 3
    max_rounds: int = 100

PRUNED = set()

def make_pool(rng):
    pool = [{"kind":"char","name":n} for n in CHARACTERS]
    for _ in range(3):
        for n in LOADOUTS:
            if n not in PRUNED: pool.append({"kind":"loadout","name":n})
    for _ in range(3):
        for n in EQUIPMENT:
            if n not in PRUNED: pool.append({"kind":"equip","name":n})
    rng.shuffle(pool); return pool

def winchester_draft(cfg, rng, drafters):
    pool = make_pool(rng); n = cfg.n_players
    picks = [[] for _ in range(n)]
    for _ in range(2):
        hands = [[pool.pop() for _ in range(12)] for _ in range(n)]
        for k in range(n+1):
            for i in range(n):
                hand = hands[(i-k) % n]
                if len(hand) > 2:
                    take = pick_cards(picks[i], hand, 2, rng, drafters[i], cfg)
                    for c in take: hand.remove(c); picks[i].append(c)
                elif len(hand) == 2:
                    hand.clear()
    return picks

def snake_draft(cfg, rng, drafters):
    n = cfg.n_players; picks = [[] for _ in range(n)]
    chars = [{"kind":"char","name":nm} for nm in CHARACTERS]; rng.shuffle(chars)
    order = list(range(n))
    for r in range(4):
        seq = order if r % 2 == 0 else order[::-1]
        for i in seq:
            if chars:
                c = pick_cards(picks[i], chars, 1, rng, drafters[i], cfg)[0]
                chars.remove(c); picks[i].append(c)
    gear = []
    for _ in range(4):
        for nm in LOADOUTS:
            if nm not in PRUNED: gear.append({"kind":"loadout","name":nm})
    for _ in range(4):
        for nm in EQUIPMENT:
            if nm not in PRUNED: gear.append({"kind":"equip","name":nm})
    rng.shuffle(gear)
    for r in range(12):
        seq = order if r % 2 == 0 else order[::-1]
        for i in seq:
            if gear:
                c = pick_cards(picks[i], gear, 1, rng, drafters[i], cfg)[0]
                gear.remove(c); picks[i].append(c)
    return picks

EFFECT_VALUE = {
    "heal_boost": 2.0, "ranged_range": 1.5,
    "no_heal": -2.5, "breach_strain": -2.0, "guard_strain": -2.0, "idle_strain": -1.5,
    "draw1": 3.0, "breach_jam": 1.5,
    "go_beyond": 1.5, "riposte": 1.0, "heal_exit": 1.5, "live_off_land": 1.0, "night_thief": 0.5,
    "flex": 1.5, "master_none": 4.0,
    "ld_move_leth":1.5,"ld_move_mit":1.5,"ld_stance":1.5,"ld_shieldcannon":1.5,"ld_bastion":2.0,
    "ld_flagelator":1.5,"ld_salve":2.0,"ld_jester":2.0,"ld_tactimancer":2.5,
    "ld_pos_leth":1.5,"ld_berserk":1.5,"ld_aoe":2.0,"ld_psionic":2.0,"ld_hexer":1.5,"ld_wellspring":2.0,
    "eq_finalvault":1.0,"eq_phase":1.0,"eq_kinetic":1.5,"eq_chip":1.5,"eq_backcap":1.5,
    "eq_recoil":1.5,"eq_cloak":1.5,"eq_gps":2.0,
    "eq_grapple":1.5,"eq_theft":2.0,"eq_hkscope":1.5,"eq_jammer":1.5,"eq_sapper":1.5,
    "eq_slipdraft":2.5,"eq_tariff":2.5,"eq_siphon":2.0,"eq_underdog":2.0,
}
def effect_value(name, kind, cfg):
    if kind == "equip":
        if not cfg.enable_equip_abilities: return 0.0
        return EFFECT_VALUE.get(EQUIPMENT[name][1], 0.0)
    if kind == "loadout":
        if not cfg.enable_loadout_abilities: return 0.0
        return EFFECT_VALUE.get(LOADOUTS[name][1], 0.0)
    if kind == "char":
        if not cfg.enable_char_abilities: return 0.0
        return EFFECT_VALUE.get(CHARACTERS[name][1], 0.0)
    return 0.0

def pick_cards(have, avail, k, rng, greedy, cfg):
    if not greedy:
        return rng.sample(avail, min(k, len(avail)))
    return sorted(avail, key=lambda c: -card_value(have, c, cfg))[:k]

def card_value(have, card, cfg):
    n_char = sum(1 for c in have if c["kind"]=="char")
    n_load = sum(1 for c in have if c["kind"]=="loadout")
    if card["kind"] == "char":
        if n_char >= 4: return 1
        stats,_ = CHARACTERS[card["name"]]
        wval = sum(stats[i]*STAT_WEIGHTS[i] for i in range(5))
        have_w = sum(CHARACTERS[c["name"]][0][W] for c in have if c["kind"]=="char")
        have_s = sum(CHARACTERS[c["name"]][0][S] for c in have if c["kind"]=="char")
        role = 0
        if have_w < 3 and stats[W] >= 2: role += 5
        if have_s < 3 and stats[S] >= 2: role += 3
        return 100 + wval + role + effect_value(card["name"],"char",cfg)
    if card["kind"] == "loadout":
        if n_load >= 4: return 3
        return (60 if n_load < n_char else 25) + effect_value(card["name"],"loadout",cfg)
    return 10 + sum(abs(x*STAT_WEIGHTS[i]) for i,x in enumerate(EQUIPMENT[card["name"]][0])) + effect_value(card["name"],"equip",cfg)

@dataclass
class Gladiator:
    name: str; base: list; quirk: str = None
    tags: set = field(default_factory=set); range_bonus: int = 0
    hp: int = 0; maxhp: int = 0; downed: bool = False; ability: str = None
    endured: bool = False
    dmg_round: int = 0; dmg_total: int = 0; no_heal: bool = False

@dataclass
class Team:
    pid: int; glads: list; quirks: set = field(default_factory=set)
    loc_idx: int = 0; trav_i: int = 0; trav_remaining: int = 0; breach_remaining: int = 0
    deck: list = field(default_factory=list); hand: list = field(default_factory=list)
    discard: list = field(default_factory=list)
    extracting: bool = False; extract_round: int = None
    finished_round: int = None; won: bool = False; eliminated: bool = False
    moved_this_turn: bool = False; healed_this_turn: bool = False; draft_score: float = 0.0
    hack_intent: int = 0; disrupted_this_turn: bool = False; tiebreak: float = 0.0
    extract_progress: int = 0; braced: bool = False
    gemheart: bool = False; holder_idx: int = -1
    temp_mods: list = field(default_factory=lambda: [0,0,0,0,0])
    attacked_this_turn: bool = False; braced_this_turn: bool = False; times_attacked: int = 0
    has_breached: bool = False

def build_team(pid, drafted, cfg, rng):
    chars = [c for c in drafted if c["kind"]=="char"]
    loadouts = [c for c in drafted if c["kind"]=="loadout"]
    equips = [c for c in drafted if c["kind"]=="equip"]
    chosen = sorted(chars, key=lambda c: -(sum(
        CHARACTERS[c["name"]][0][i]*STAT_WEIGHTS[i] for i in range(5))
        + effect_value(c["name"], "char", cfg)))[:4]
    if not chosen: chosen = [{"kind":"char","name":"Khan"}]
    glads = []; used_load = set(); used_equip = set()
    for c in chosen:
        stats, quirk = CHARACTERS[c["name"]]; stats = list(stats)
        tags = set(); rbonus = 0; ability = None
        n_slots = 2 if (cfg.enable_char_abilities and quirk == "master_none") else 1
        for _ in range(n_slots):
            best = None; bestv = -1
            for li, lo in enumerate(loadouts):
                if li in used_load: continue
                tagged = LOADOUTS[lo["name"]][0]; val = sum(stats[t] for t in tagged)
                if val > bestv: bestv = val; best = li
            if best is not None:
                used_load.add(best); tagged, ab, tag = LOADOUTS[loadouts[best]["name"]]
                for t in tagged: stats[t] += cfg.loadout_bonus
                if tag: tags.add(tag)
                if ab: tags.add(ab); ability = ability or ab
        avail_eq = [(ei,e) for ei,e in enumerate(equips) if ei not in used_equip]
        avail_eq.sort(key=lambda x: -(sum(abs(v) for v in EQUIPMENT[x[1]["name"]][0]) + effect_value(x[1]["name"],"equip",cfg)))
        for ei, e in avail_eq[:3]:
            used_equip.add(ei); delta, etag = EQUIPMENT[e["name"]]
            for i in range(5): stats[i] += delta[i]
            if etag == "ranged_range": rbonus += 1; tags.add("ranged")
            elif etag in ("melee","ranged"): tags.add(etag)
            elif etag == "eq_serrated": tags.add("melee"); tags.add("eq_chip")
            elif etag in ("heal_boost",): ability = ability or "heal_boost"
            elif etag: tags.add(etag)
        tags -= cfg.disabled_effects
        if ability in cfg.disabled_effects: ability = None
        if quirk in cfg.disabled_effects: quirk = None
        stats = [max(0, x) for x in stats]
        if quirk == "sniper": rbonus += 1
        hp = max(1, stats[V])
        gl = Gladiator(c["name"], stats, quirk, tags, rbonus, hp, hp, False, ability)
        gl.no_heal = "no_heal" in tags
        glads.append(gl)
    team = Team(pid, glads)
    team.quirks = {g.quirk for g in glads if g.quirk}
    if cfg.econ_deck:
        deck = (["MA"]*cfg.deck_MA2 + ["MB"]*cfg.deck_MB2 + ["BA"]*cfg.deck_BA2
                + ["HD"]*cfg.deck_HD + ["DR"]*cfg.deck_DR + ["RH"]*cfg.deck_RH)
    elif cfg.hybrid_progress_deck:
        deck = (["MB"]*cfg.deck_sM + ["sA"]*cfg.deck_sA + ["sD"]*cfg.deck_sD + ["sH"]*cfg.deck_sH)
    elif cfg.single_basics:
        deck = (["sM"]*cfg.deck_sM + ["sA"]*cfg.deck_sA + ["sB"]*cfg.deck_sB
                + ["sD"]*cfg.deck_sD + ["sH"]*cfg.deck_sH)
    else:
        deck = (["MA"]*cfg.deck_MA + ["MB"]*cfg.deck_MB + ["BA"]*cfg.deck_BA + ["H"]*cfg.deck_H)
        if cfg.new_combat:
            deck += ["MD"]*cfg.deck_MD + ["BD"]*cfg.deck_BD + ["AD"]*cfg.deck_AD
    rng.shuffle(deck); team.deck = deck
    team.draft_score = team_strength(team, cfg)
    return team

def team_strength(team, cfg):
    p = pooled(team, cfg, False, full=True)
    hp = sum(g.maxhp for g in team.glads)
    stat_val = sum(p[i]*STAT_WEIGHTS[i] for i in range(5)) + hp*0.15
    eff_val = 0.0
    for g in team.glads:
        if g.quirk: eff_val += EFFECT_VALUE.get(g.quirk, 0.0)
        for tag in g.tags: eff_val += EFFECT_VALUE.get(tag, 0.0)
    return stat_val + eff_val

def active_quirks(t):
    return {g.quirk for g in t.glads if g.quirk and not g.downed}

def has_ability(t, name):
    return any(g.ability == name and not g.downed for g in t.glads)

def gear_temp(team, cfg, track):
    m = [0,0,0,0,0]
    lo = cfg.enable_loadout_abilities; eq = cfg.enable_equip_abilities
    if not (lo or eq): return m
    moved = team.moved_this_turn; atkd = team.attacked_this_turn; brcd = team.braced_this_turn
    final_vault = team.loc_idx == N_LOC-1
    not_ldr = not getattr(team, "is_leader_now", False)
    for g in team.glads:
        if g.downed: continue
        T = g.tags
        if lo:
            if "ld_move_leth" in T and moved: m[L]+=2
            if "ld_move_mit" in T and moved: m[M]+=2
            if "ld_stance" in T:
                if atkd: m[L]+=2; m[M]-=1
                elif brcd: m[M]+=2; m[L]-=1
            if "ld_shieldcannon" in T and atkd: m[L]+=2
            if "ld_bastion" in T and team.times_attacked>0: m[M]+=min(ABILITY_CAP, 4*team.times_attacked)
        if eq:
            if "eq_finalvault" in T and final_vault: m[W]+=2
            if "eq_phase" in T and moved: m[W]+=1
            if "eq_kinetic" in T: m[S]+=min(ABILITY_CAP, g.dmg_total)
            if "eq_grapple" in T and not_ldr: m[S]+=2
            if "eq_theft" in T: m[W]+= (3 if not_ldr else -1)
            if "eq_slipdraft" in T and not_ldr: m[S]+= getattr(team, "leader_gap", 0)
    if eq and getattr(team, "is_last_now", False) and any("eq_underdog" in g.tags for g in team.glads if not g.downed):
        tot = [sum(g.base[i] for g in team.glads if not g.downed) + m[i] for i in range(5)]
        m[min(range(5), key=lambda i: tot[i])] += 3   # Underdog: +3 to lowest stat in last place
    if eq and getattr(team, "is_leader_now", False):
        m[W]-=getattr(team, "ext_w_pen", 0); m[S]-=getattr(team, "ext_s_pen", 0)
    return m

def pooled(team, cfg, halfw, full=False):
    cf = 1.0 if full else cfg.down_factor
    sf = 1.0 if full else cfg.down_speed_factor
    mode = cfg.down_round_mode
    tot = [0.0]*5
    for g in team.glads:
        if g.downed:
            c = [g.base[L]*cf, g.base[M]*cf, g.base[S]*sf, g.base[V]*cf, g.base[W]*cf]
            if mode == "ceil":   c = [math.ceil(x) for x in c]
            elif mode == "floor": c = [math.floor(x) for x in c]
            tot[L]+=c[0]; tot[M]+=c[1]; tot[S]+=c[2]; tot[V]+=c[3]; tot[W]+=c[4]
        else:
            for i in range(5): tot[i] += g.base[i]
    if "eager" in active_quirks(team):
        if cfg.enable_char_abilities:
            if not team.has_breached: tot[S] += 3
        elif halfw:
            tot[S] += 3
    for i in range(5): tot[i] += team.temp_mods[i]
    gm = gear_temp(team, cfg, track=None)
    for i in range(5): tot[i] += gm[i]
    return [max(0, int(round(x))) for x in tot]

def at_hack(t, track): return track[t.loc_idx].breach > 0
def halfway(t): return t.loc_idx >= 4

def race_leader(teams):
    active = [t for t in teams if t.finished_round is None]
    if not active: return None
    s = sorted(active, key=lambda t: (t.loc_idx, -t.trav_remaining), reverse=True)
    if len(s) >= 2 and (s[0].loc_idx, -s[0].trav_remaining) == (s[1].loc_idx, -s[1].trav_remaining):
        return None  # exact tie for first => no leader
    return s[0]

def race_last(teams):
    active = [t for t in teams if t.finished_round is None]
    if not active: return None
    s = sorted(active, key=lambda t: (t.loc_idx, -t.trav_remaining))
    if len(s) >= 2 and (s[0].loc_idx, -s[0].trav_remaining) == (s[1].loc_idx, -s[1].trav_remaining):
        return None  # exact tie for last => no clear underdog
    return s[0]
def team_wiped(t): return all(g.downed for g in t.glads)
def any_downed(t): return any(g.downed for g in t.glads)

def draw_hand(team, cfg, rng):
    hsize = cfg.hand_size + (2 if "tactician" in active_quirks(team) else 0)
    ndraw = cfg.draw_per_turn + sum(
        1 for g in team.glads if g.ability=="draw1" and not g.downed)
    for _ in range(ndraw):
        if not team.deck:
            team.deck = team.discard; team.discard = []; rng.shuffle(team.deck)
        if team.deck: team.hand.append(team.deck.pop())
    if cfg.enable_loadout_abilities and ndraw > 0 and any("ld_jester" in g.tags for g in team.glads if not g.downed):
        add_temp(team, L, ndraw, "jester")
    while len(team.hand) > hsize: team.discard.append(team.hand.pop())

def _draw_n(team, cfg, rng, n):
    hsize = cfg.hand_size + (2 if "tactician" in active_quirks(team) else 0)
    for _ in range(n):
        if not team.deck:
            team.deck = team.discard; team.discard = []; rng.shuffle(team.deck)
        if team.deck and len(team.hand) < hsize:
            team.hand.append(team.deck.pop())

def _do_regroup(team, cfg, rng):
    _draw_n(team, cfg, rng, cfg.regroup_yield)
    if cfg.enable_loadout_abilities and any("ld_tactimancer" in g.tags for g in team.glads if not g.downed):
        _draw_n(team, cfg, rng, 1); add_temp(team, M, 1, "tactimancer")

def attack_reach(t, cfg):
    return cfg.base_reach + max((g.range_bonus for g in t.glads if not g.downed), default=0)

def ranged_dir_ok(attacker, d, reach, cfg):
    """d = target.loc_idx - attacker.loc_idx (nonzero). Is a ranged attack allowed by direction/reach?"""
    if d > 0: return d <= reach            # forward: always allowed within reach
    if -d > reach: return False            # backward but out of reach
    if not cfg.ranged_forward_only: return True                       # free-fire mode
    return cfg.leader_backward_ranged and getattr(attacker, "is_leader_now", False)  # leader-only backward

def best_attack_target(team, teams, cfg, track):
    cands = []
    if track[team.loc_idx].effect == "safe": return None
    for o in teams:
        if o is team or o.finished_round is not None: continue
        if track[o.loc_idx].effect == "safe": continue
        d = o.loc_idx - team.loc_idx; reach = attack_reach(team, cfg)
        in_melee = (d == 0)
        in_ranged = (d != 0) and ranged_dir_ok(team, d, reach, cfg)
        if in_melee or in_ranged: cands.append((o, in_melee))
    if not cands: return None
    cands.sort(key=lambda c: (-c[0].loc_idx, not c[1], c[0].tiebreak))
    return cands[0][0]

def gate_disrupt_target(team, teams, track):
    if track[team.loc_idx].breach <= 0: return None
    cands = []
    for o in teams:
        if o is team or o.finished_round is not None: continue
        if o.loc_idx != team.loc_idx: continue
        if track[o.loc_idx].breach <= 0: continue
        if o.breach_remaining < team.breach_remaining:
            cands.append(o)
    if not cands: return None
    return min(cands, key=lambda o: (o.breach_remaining, o.tiebreak))

def extract_deny_target(team, teams, cfg, track):
    reach = attack_reach(team, cfg)
    cands = []
    for o in teams:
        if o is team or o.finished_round is not None or not o.extracting: continue
        d = o.loc_idx - team.loc_idx
        in_range = (d == 0) or ranged_dir_ok(team, d, reach, cfg)
        if in_range: cands.append(o)
    if not cands: return None
    return max(cands, key=lambda o: (o.extract_progress, o.tiebreak))

def incoming_threat(team, teams, cfg, track):
    tp = pooled(team, cfg, halfway(team)); mit = tp[M] // cfg.combat_div if cfg.combat_div>1 else tp[M]
    worst = 0
    for o in teams:
        if o is team or o.finished_round is not None: continue
        d = team.loc_idx - o.loc_idx; reach = attack_reach(o, cfg)
        in_range = (d==0) or ranged_dir_ok(o, d, reach, cfg)
        if not in_range: continue
        val = compute_attack(o, team, cfg, track)
        worst = max(worst, val - mit)
    return worst

def count_downs_from(team, dmg):
    hps = [g.hp for g in team.glads if not g.downed]
    for _ in range(int(dmg)):
        if not hps: break
        i = max(range(len(hps)), key=lambda j: hps[j]); hps[i] -= 1
    return sum(1 for h in hps if h <= 0)

def gate_tension_eval(team, rival, cfg, track):
    pT = pooled(team, cfg, halfway(team)); pR = pooled(rival, cfg, halfway(rival))
    myW = max(1.0, float(pT[W])); rW = max(1.0, float(pR[W]))
    dmg_me = max(0, compute_attack(rival, team, cfg, track) - pT[M])
    cost = 0.5*dmg_me + 2.0*count_downs_from(team, dmg_me)
    q = cfg.gate_attack_prob
    scale = myW
    evb_n = myW - rW
    eva_n = (1-q)*(myW - rW) + q*(-cost)
    evb_f = (1-q)*(myW - rW) + q*(-rW)
    eva_f = (1-q)*(myW)      + q*(-cost)
    return (evb_n - eva_n)/scale, (evb_f - eva_f)/scale

def choose_actions(team, teams, cfg, track, rng):
    if cfg.new_combat:
        return choose_actions_v2(team, teams, cfg, track, rng)
    return choose_actions_v1(team, teams, cfg, track, rng)

def take_card(team, want, cfg=None):
    if want == "breach" and cfg is not None and cfg.burn_to_hack and team.hand:
        card = next((c for c in team.hand if "breach" in CARD_TYPES[c]), team.hand[0])
        team.hand.remove(card); team.discard.append(card); return "breach"
    card = next((c for c in team.hand if want in CARD_TYPES[c]), None)
    if card is None and want in ("attack","defend") and cfg is not None and cfg.enable_char_abilities and "flex" in active_quirks(team):
        other = "defend" if want == "attack" else "attack"
        card = next((c for c in team.hand if other in CARD_TYPES[c]), None)
        if card is not None:
            team.hand.remove(card); team.discard.append(card); return want
    if card is None and team.hand: card = team.hand[0]
    if card is None: return None
    team.hand.remove(card); team.discard.append(card)
    opts = CARD_TYPES[card]
    if want in opts: return want
    return next((o for o in ("breach","move","defend","attack","heal") if o in opts), opts[0])

def choose_actions_v2(team, teams, cfg, track, rng):
    active = [o for o in teams if o.finished_round is None and o is not team]
    trailing = any(o.loc_idx > team.loc_idx for o in active)
    aggro = cfg.catchup_aggro if (cfg.focus_leader and trailing) else 0.45
    at_gate = at_hack(team, track) and team.breach_remaining > 0
    deny = extract_deny_target(team, teams, cfg, track)
    dt = gate_disrupt_target(team, teams, track) if at_gate else None
    tgt = best_attack_target(team, teams, cfg, track)
    threat = incoming_threat(team, teams, cfg, track)
    if cfg.regroup:
        _REGROUP["turns"] += 1
        calm = (not team.extracting and not at_gate and deny is None
                and threat < cfg.brace_min_threat)
        if len(team.hand) == 0:
            _do_regroup(team, cfg, rng); _REGROUP["regroups"] += 1; _REGROUP["forced"] += 1
            return []
        wants = {"move"}
        if at_gate and team.breach_remaining > 0: wants.add("breach")
        if dt is not None or deny is not None: wants.add("attack")
        if team.extracting: wants.update({"move", "defend"})
        if any_downed(team): wants.update({"heal", "move"})
        if threat >= cfg.brace_min_threat: wants.add("defend")
        if tgt is not None: wants.add("attack")
        useful = any(set(CARD_TYPES[c]) & wants for c in team.hand)
        if calm and (not useful or len(team.hand) <= 1):
            _do_regroup(team, cfg, rng); _REGROUP["regroups"] += 1; _REGROUP["voluntary"] += 1
            return []
    runner = team.extracting and cfg.vault_extract_counter > 0
    inversion = cfg.vault_extract_counter > 0 and any(o.extracting for o in teams)
    if runner:
        progress = "move"
        if threat >= cfg.brace_min_threat and rng.random() < cfg.brace_threat_prob:
            combat, ctgt = "defend", None
        elif cfg.allow_sprint and rng.random() < 0.7:
            combat, ctgt = "move", None
        else:
            combat, ctgt = ("defend", None) if threat > 0 else ("move", None)
        return _commit_v2(team, progress, combat, ctgt, tgt, cfg, at_gate, threat, teams, track)
    if inversion and not team.extracting:
        prog = "move"
        run_t = next((o for o in teams if o.extracting and o.finished_round is None), None)
        in_rng = run_t is not None and (run_t.loc_idx == team.loc_idx or
                 (0 < run_t.loc_idx - team.loc_idx <= attack_reach(team, cfg)))
        if run_t is not None and in_rng:
            combat, ctgt = "attack", run_t
        elif cfg.allow_sprint:
            combat, ctgt = "move", None
        else:
            combat, ctgt = "attack", run_t
        return _commit_v2(team, prog, combat, ctgt, tgt, cfg, at_gate, threat, teams, track)
    progress = "breach" if (at_gate or team.extracting) else "move"
    if any_downed(team) and any("heal" in CARD_TYPES[c] for c in team.hand) and rng.random()<0.6:
        combat, ctgt = "heal", None
    elif deny is not None and rng.random() < max(cfg.gate_attack_prob, 0.85):
        combat, ctgt = "attack", deny
    elif dt is not None and rng.random() < cfg.gate_attack_prob:
        combat, ctgt = "attack", dt
    elif threat >= cfg.brace_min_threat and rng.random() < cfg.brace_threat_prob:
        combat, ctgt = "defend", None
    elif tgt is not None and rng.random() < aggro:
        combat, ctgt = "attack", tgt
    elif (not at_gate) and (not team.extracting) and cfg.allow_sprint and trailing:
        combat, ctgt = "move", None
    else:
        combat, ctgt = ("defend", None) if threat > 0 else ("move", None)
    if (cfg.econ_deck and combat in ("move", "defend") and threat < cfg.brace_min_threat
            and not at_gate and not team.extracting and deny is None
            and len(team.hand) <= cfg.draw_card_amount + 1
            and any("draw" in CARD_TYPES[c] for c in team.hand)):
        combat, ctgt = "draw", None
    return _commit_v2(team, progress, combat, ctgt, tgt, cfg, at_gate, threat, teams, track, dt, deny)

def _commit_v2(team, progress, combat, ctgt, tgt, cfg, at_gate, threat, teams, track, dt=None, deny=None):
    if combat == progress and combat != "move":
        combat = "defend" if combat != "defend" else "move"
    if team.pid in cfg.pacifist_pids and combat == "attack":
        combat, ctgt = ("defend", None) if threat > 0 else ("move", None)
        if combat == progress and combat != "move":
            combat = "defend"
        if combat == "move" and progress != "move" and not cfg.allow_sprint:
            combat = "defend"
    colocated = any(o is not team and o.finished_round is None and o.loc_idx == team.loc_idx for o in teams)
    if cfg.measure_yomi and colocated and (at_gate or team.extracting):
        _YOMI["standoff"] += 1
        can_progress = at_gate or team.extracting
        can_attack   = (tgt is not None) or (dt is not None) or (deny is not None)
        can_brace    = threat > 0
        can_heal     = any_downed(team)
        if (int(can_progress)+int(can_attack)+int(can_brace)+int(can_heal)) >= 2:
            _YOMI["multi"] += 1
    if combat == "attack": _COMBAT["attacks"] += 1
    elif combat == "defend": _COMBAT["braces"] += 1
    elif combat == "move" and progress == "move": _COMBAT["sprints"] += 1
    if at_gate and colocated:
        _COMBAT["gate_dec"] += 1
        if combat == "attack": _COMBAT["gate_atk"] += 1
        elif combat == "defend": _COMBAT["gate_brace"] += 1
    if cfg.measure_tension and at_gate:
        rivals = [o for o in teams if o is not team and o.finished_round is None
                  and o.loc_idx == team.loc_idx and track[o.loc_idx].breach > 0]
        if rivals:
            rival = max(rivals, key=lambda o: pooled(o,cfg,halfway(o))[L] + pooled(o,cfg,halfway(o))[W])
            gn, gf = gate_tension_eval(team, rival, cfg, track)
            _TENSION["gn"].append(gn); _TENSION["gf"].append(gf)
    out = []
    p = take_card(team, progress, cfg)
    if p == "attack":   out.append(("attack", tgt))
    elif p == "breach": out.append(("breach", None))
    elif p == "defend": out.append(("defend", None))
    elif p == "heal":   out.append(("heal", None))
    elif p == "draw":   out.append(("draw", None))
    elif p is not None: out.append(("move", None))
    if team.hand:
        c = take_card(team, combat, cfg)
        if c == "attack":   out.append(("attack", ctgt if ctgt is not None else tgt))
        elif c == "breach": out.append(("breach", None))
        elif c == "defend": out.append(("defend", None))
        elif c == "heal":   out.append(("heal", None))
        elif c == "draw":   out.append(("draw", None))
        elif c is not None: out.append(("move", None))
    return out

def choose_actions_v1(team, teams, cfg, track, rng):
    actions = []
    trailing = False
    if cfg.focus_leader:
        active = [o for o in teams if o.finished_round is None]
        trailing = any(o.loc_idx > team.loc_idx for o in active if o is not team)
    aggro = cfg.catchup_aggro if (cfg.focus_leader and trailing) else 0.45
    for _ in range(cfg.actions_per_turn):
        if not team.hand: break
        loc = track[team.loc_idx]
        deny = extract_deny_target(team, teams, cfg, track)
        if any_downed(team) and any("heal" in CARD_TYPES[c] for c in team.hand) and rng.random()<0.6:
            want = "heal"; _forced_target = None
        elif team.extracting:
            if deny is not None and deny.extract_progress >= team.extract_progress and rng.random() < cfg.gate_attack_prob:
                want = "attack"; _forced_target = deny
            else:
                want = "breach"; _forced_target = None
        elif deny is not None:
            if rng.random() < max(cfg.gate_attack_prob, 0.85):
                want = "attack"; _forced_target = deny
            else:
                want = "breach" if (at_hack(team, track) and team.breach_remaining > 0) else "move"
                _forced_target = None
        elif at_hack(team, track) and team.breach_remaining > 0:
            dt = gate_disrupt_target(team, teams, track)
            if dt is not None and rng.random() < cfg.gate_attack_prob:
                want = "attack"; _forced_target = dt
            else:
                want = "breach"; _forced_target = None
        else:
            _forced_target = None
            tgt = best_attack_target(team, teams, cfg, track)
            if tgt is not None and rng.random() < aggro: want = "attack"
            else: want = "move"
        if cfg.measure_yomi:
            colocated = any(o is not team and o.finished_round is None and o.loc_idx == team.loc_idx for o in teams)
            if colocated and (at_hack(team, track) or team.extracting):
                _YOMI["standoff"] += 1
                can_progress = (team.extracting or team.breach_remaining > 0)
                can_deny = (deny is not None) or (gate_disrupt_target(team, teams, track) is not None)
                can_heal = any_downed(team)
                if (int(can_progress) + int(can_deny) + int(can_heal)) >= 2:
                    _YOMI["multi"] += 1
        card = next((c for c in team.hand if want in CARD_TYPES[c]), None)
        if card is None: card = team.hand[0]
        team.hand.remove(card); team.discard.append(card)
        opts = CARD_TYPES[card]
        if want in opts: chosen = want
        else:
            chosen = next((o for o in ("move","breach","attack","heal") if o in opts), opts[0])
        if chosen == "attack":
            tgt = _forced_target if _forced_target is not None else best_attack_target(team, teams, cfg, track)
            actions.append(("attack", tgt))
        elif chosen == "breach":
            actions.append(("breach", None))
        elif chosen == "heal":
            actions.append(("heal", None))
        else:
            actions.append(("move", None))
    return actions

def compute_attack(team, target, cfg, track):
    halfw = halfway(team); p = pooled(team, cfg, halfw)
    leth = p[L] // cfg.combat_div if cfg.combat_div > 1 else p[L]
    val = cfg.attack_floor + min(leth, cfg.l_bonus_cap)
    d = target.loc_idx - team.loc_idx; is_melee = (d == 0)
    loc = track[team.loc_idx]; tloc = track[target.loc_idx]
    melee_tag = any("melee" in g.tags for g in team.glads if not g.downed)
    ranged_tag = any("ranged" in g.tags for g in team.glads if not g.downed)
    if is_melee:
        if melee_tag: val += 1
        if "brawler" in active_quirks(team): val += (2 if cfg.enable_char_abilities else 1)
        if loc.effect=="meleeboost" or tloc.effect=="meleeboost": val += 2
    else:
        if ranged_tag: val += 1
        if loc.effect=="rangeboost" or tloc.effect=="rangeboost": val += 2
        if tloc.effect=="rangeguard": val -= 4
    if "momentum" in active_quirks(team) and team.moved_this_turn: val += 1
    if cfg.enable_loadout_abilities:
        if any("ld_pos_leth" in g.tags for g in team.glads if not g.downed):
            val += -1 if is_melee else 1   # Cyberhawk: reward attacking out of location
        for g in team.glads:               # Psionic: use W-as-L when attacking if higher #APPROX
            if not g.downed and "ld_psionic" in g.tags and g.base[W] > g.base[L]:
                val += g.base[W] - g.base[L]
    if cfg.enable_equip_abilities and getattr(target, "is_leader_now", False) \
            and any("eq_hkscope" in g.tags for g in team.glads if not g.downed):
        val += 2   # Hunter Killer Scope: +2 L vs the Leader
    return val

def resolve_attack(team, target, cfg, track, teams=None):
    if target is None or target.finished_round is not None: return 0
    d = target.loc_idx - team.loc_idx; reach = attack_reach(team, cfg)
    in_range = (d==0) or ranged_dir_ok(team, d, reach, cfg)
    if not in_range: return 0
    val = compute_attack(team, target, cfg, track)
    tp = pooled(target, cfg, halfway(target))
    mit = tp[M] // cfg.combat_div if cfg.combat_div > 1 else tp[M]
    if cfg.new_combat and getattr(target, "braced", False):
        mit += tp[M] // cfg.combat_div if cfg.combat_div > 1 else tp[M]
    if "intimidate" in active_quirks(target): val -= 1
    is_ranged = (target.loc_idx - team.loc_idx) != 0
    if cfg.enable_equip_abilities and is_ranged and any("eq_backcap" in g.tags for g in target.glads if not g.downed):
        val -= 1
    if cfg.enable_loadout_abilities:   # VoltBerserker: spend min HP to break through mit #APPROX
        bh = next((g for g in team.glads if not g.downed and "ld_berserk" in g.tags and g.hp >= 2), None)
        if bh is not None and val <= mit:
            invest = min(mit - val + 1, bh.hp - 1, ABILITY_CAP)
            if invest > 0:
                val += invest
                deal_to_gladiator(bh, invest)
    if cfg.uncapped:
        dmg = max(0, val - mit)
    else:
        dmg = min(max(0, val - mit), cfg.damage_cap)
    if dmg > 0:
        before = sum(g.dmg_total for g in target.glads)
        downs_before = sum(1 for g in target.glads if g.downed)
        allocate_damage(target, dmg)
        if cfg.down_stagger:
            new_downs = sum(1 for g in target.glads if g.downed) - downs_before
            if new_downs > 0:
                target.trav_remaining += cfg.down_stagger * new_downs   # downing slows the victim's race
        if cfg.enable_char_abilities and sum(g.dmg_total for g in target.glads) > before:
            if has_ability(target, "go_beyond") or "go_beyond" in active_quirks(target):
                need = pooled(target, cfg, halfway(target))
                stat = min(range(5), key=lambda i: need[i])
                add_temp(target, stat, 1, "gideon")
            if ("riposte" in active_quirks(target) or has_ability(target, "riposte")) and team.hand:
                card = team.hand.pop()
                team.discard.append(card)
                if "night_thief" in active_quirks(team) or has_ability(team, "night_thief"):
                    if target.hand: target.discard.append(target.hand.pop())
        if cfg.enable_equip_abilities and target.hand and any("guard_strain" in g.tags for g in target.glads if not g.downed):
            target.discard.append(target.hand.pop())
        if track[target.loc_idx].breach > 0:
            melee = (target.loc_idx - team.loc_idx) == 0
            if not (cfg.vault_extract_counter > 0 and target.extracting and not melee):
                target.disrupted_this_turn = True
    if cfg.enable_equip_abilities:
        is_melee = (target.loc_idx - team.loc_idx) == 0
        if is_melee and any("eq_chip" in g.tags for g in team.glads if not g.downed):
            deal_direct(target, 1)
        if is_ranged and any("eq_recoil" in g.tags for g in team.glads if not g.downed):
            add_temp(team, M, 2, "recoil")
        if any("eq_cloak" in g.tags for g in target.glads if not g.downed):
            add_temp(team, M, -2); add_temp(team, S, -2)
    if cfg.enable_loadout_abilities and dmg > 0 and any("ld_flagelator" in g.tags for g in target.glads if not g.downed):
        deal_direct(team, 1)
    if teams is not None and is_ranged and cfg.enable_loadout_abilities \
            and any("ld_aoe" in g.tags for g in team.glads if not g.downed):
        for o in teams:   # SurgeBomber: ranged attack splashes all teams at target location
            if o is team or o is target or o.finished_round is not None: continue
            if o.loc_idx == target.loc_idx:
                resolve_attack(team, o, cfg, track, teams=None)
    return dmg

def allocate_damage(target, dmg):
    for _ in range(dmg):
        standing = [g for g in target.glads if not g.downed]
        if not standing: break
        g = max(standing, key=lambda x: x.hp)
        if g.quirk=="endure" and not g.endured:
            g.endured = True; continue
        g.hp -= 1; g.dmg_round += 1; g.dmg_total += 1
        if g.hp <= 0: g.downed = True; g.hp = 0

def deal_direct(target, amount):
    allocate_damage(target, amount)

def deal_to_gladiator(glad, amount):
    """Deal damage directly to a specific gladiator (equipment drawbacks)."""
    for _ in range(amount):
        if glad.downed: break
        if glad.quirk == "endure" and not glad.endured:
            glad.endured = True; continue
        glad.hp -= 1; glad.dmg_round += 1; glad.dmg_total += 1
        if glad.hp <= 0: glad.downed = True; glad.hp = 0

def deal_to_holder(team, tag, amount):
    """Deal drawback damage to the gladiator assigned the item with the given tag."""
    holder = next((g for g in team.glads if tag in g.tags and not g.downed), None)
    if holder:
        deal_to_gladiator(holder, amount)

def resolve_move(team, teams, cfg, track):
    if team.extracting and cfg.vault_extract_counter > 0:
        eff = max(1, pooled(team, cfg, halfway(team))[S] - cfg.gemheart_speed_penalty)
        team.hack_intent += eff; team.moved_this_turn = True
        return
    loc = track[team.loc_idx]; halfw = halfway(team)
    speed = pooled(team, cfg, halfw)[S] + loc.smod
    if "ghoststep" in active_quirks(team) and loc.smod < 0: speed += (2 if cfg.enable_char_abilities else 1)
    ndown = sum(1 for g in team.glads if g.downed)
    speed -= cfg.down_drag * ndown
    if ndown > 0 and cfg.down_team_move_factor != 1.0:
        speed = max(1, speed * cfg.down_team_move_factor)   # whole-team movement penalty while any down; floored at 1
    if cfg.trailblazer_drag or cfg.slipstream_bonus:
        active = [o for o in teams if o.finished_round is None]
        if len(active) > 1:
            lead = max(active, key=lambda o: (o.loc_idx, -o.trav_remaining, -o.breach_remaining, o.tiebreak))
            ahead = any(o.loc_idx > team.loc_idx for o in active if o is not team)
            if team is lead and team.loc_idx > 0:
                speed -= cfg.trailblazer_drag
            if ahead:
                if cfg.slipstream_graduated:
                    behind = max(0, lead.loc_idx - team.loc_idx)
                    speed += cfg.slipstream_bonus * behind
                else:
                    speed += cfg.slipstream_bonus
    if cfg.enable_loadout_abilities:   # Hexer: enemies sharing your location move -2 Speed
        for o in teams:
            if o is not team and o.finished_round is None and o.loc_idx == team.loc_idx \
                    and any("ld_hexer" in g.tags for g in o.glads if not g.downed):
                speed -= 2; break
    speed = max(0, int(round(speed)))
    if team.trav_remaining <= 0 and team.trav_i < len(loc.trav):
        team.trav_remaining = loc.trav[team.trav_i]
    team.trav_remaining -= speed; team.moved_this_turn = True
    if team.trav_remaining <= 0:
        team.trav_i += 1; team.trav_remaining = 0
        if team.trav_i >= len(loc.trav):
            if loc.breach > 0 and team.breach_remaining > 0: pass
            else: advance(team, teams, cfg, track)
        else:
            team.trav_remaining = loc.trav[team.trav_i]

def advance(team, teams, cfg, track):
    if team.loc_idx >= N_LOC-1: return
    team.loc_idx += 1; team.trav_i = 0
    loc = track[team.loc_idx]
    team.trav_remaining = loc.trav[0] if loc.trav else 0
    team.breach_remaining = loc.breach
    if cfg.first_entry_penalty and not any(
            o is not team and o.finished_round is None and o.loc_idx >= team.loc_idx for o in teams):
        pen = cfg.first_entry_penalty
        if cfg.enable_equip_abilities and getattr(team, "is_leader_now", False):
            ntar = sum(1 for o in teams if o is not team and o.finished_round is None
                       and any("eq_tariff" in g.tags for g in o.glads if not g.downed))
            pen += 2 * ntar
        team.trav_remaining += pen
    if cfg.enable_char_abilities and "heal_exit" in active_quirks(team):
        heal_team(team, 1, cfg)
    if cfg.enable_equip_abilities and any("eq_gps" in g.tags for g in team.glads if not g.downed):
        team.gps_pending = getattr(team, "gps_pending", 0) + 1   # GPS: draw on traversal resolve
    if loc.effect == "heal": heal_team(team, 1, cfg)

def resolve_breach(team, teams, cfg, track, rng=None):
    if cfg.enable_equip_abilities and not team.extracting and any("breach_strain" in g.tags for g in team.glads if not g.downed):
        if not (cfg.soften_drawbacks and rng is not None and rng.random() < 0.5):
            deal_to_holder(team, "breach_strain", 1)
    if team.extracting:
        if cfg.vault_extract_counter > 0:
            return
        team.hack_intent += (pooled(team, cfg, halfway(team))[W] if cfg.extract_mode=="hack" else 1)
        return
    loc = track[team.loc_idx]
    if loc.breach <= 0 or team.breach_remaining <= 0: return
    p = pooled(team, cfg, halfway(team))
    team.hack_intent += p[W]
    if cfg.speed_breach_frac:
        team.hack_intent += int(cfg.speed_breach_frac * p[S])   # surplus Speed helps breach
    if cfg.enable_loadout_abilities:   # Psionic: use L-as-W when breaching if higher #APPROX
        for g in team.glads:
            if not g.downed and "ld_psionic" in g.tags and g.base[L] > g.base[W]:
                team.hack_intent += g.base[L] - g.base[W]
    if cfg.enable_equip_abilities and getattr(team, "is_leader_now", False):
        for o in teams:   # Vault Siphon: trailing holders advance when the Leader breaches
            if o is team or o.finished_round is not None: continue
            if any("eq_siphon" in g.tags for g in o.glads if not g.downed):
                o.breach_remaining = max(0, o.breach_remaining - 1)

def apply_hack(team, teams, cfg, track):
    if team.extracting:
        holder_down = (cfg.vault_extract_counter > 0 and 0 <= team.holder_idx < len(team.glads)
                       and team.glads[team.holder_idx].downed)
        if team.disrupted_this_turn and cfg.extract_disrupt == "freeze":
            pass
        elif holder_down:
            pass
        else:
            team.extract_progress += team.hack_intent
        team.hack_intent = 0; team.disrupted_this_turn = False
        return
    loc = track[team.loc_idx]
    if loc.breach <= 0 or team.breach_remaining <= 0:
        team.hack_intent = 0; team.disrupted_this_turn = False; return
    interf = 0
    for o in teams:
        if o is team or o.finished_round is not None: continue
        if o.loc_idx == team.loc_idx:
            if "comphacker" in active_quirks(o): interf += 1
            if cfg.enable_loadout_abilities and any("breach_jam" in g.tags for g in o.glads if not g.downed): interf += 1
            if any(g.ability=="breach_jam" for g in o.glads if not g.downed): interf += 1
    if team.disrupted_this_turn and cfg.hack_disrupt == "freeze":
        progress = 0
    elif team.disrupted_this_turn and cfg.hack_disrupt == "pushback":
        progress = -cfg.pushback_amount
    else:
        progress = team.hack_intent
    team.breach_remaining = max(0, team.breach_remaining + interf - progress)
    team.hack_intent = 0; team.disrupted_this_turn = False
    if team.breach_remaining == 0 and track[team.loc_idx].breach > 0:
        team.has_breached = True
    if team.breach_remaining == 0 and team.trav_i >= len(loc.trav):
        if team.loc_idx == N_LOC-1:
            already = any(o.extracting for o in teams if o is not team)
            if cfg.vault_extract_counter > 0 and already:
                pass
            else:
                team.extracting = True; team.extract_progress = 0
                if cfg.vault_extract_counter > 0:
                    team.gemheart = True
                    standing = [i for i,g in enumerate(team.glads) if not g.downed]
                    team.holder_idx = max(standing, key=lambda i: team.glads[i].hp) if standing else 0
        else: advance(team, teams, cfg, track)

def heal_team(team, amount, cfg):
    boost = 0
    if "healtouch" in active_quirks(team): boost += 1
    if has_ability(team, "heal_boost"): boost += 1
    if cfg.easy_revive: boost += 1
    amount += boost; team.healed_this_turn = True
    restored = False
    for g in sorted(team.glads, key=lambda x: (not x.downed, x.hp)):
        if amount <= 0: break
        if g.downed: g.downed=False; g.hp=1; amount-=1; restored=True
        elif g.hp < g.maxhp and not (cfg.enable_equip_abilities and getattr(g,"no_heal",False)):
            h = min(amount, g.maxhp-g.hp); g.hp += h; amount -= h; restored=True
    if restored and cfg.enable_loadout_abilities and any("ld_wellspring" in g.tags for g in team.glads if not g.downed):
        team.wellspring_pending = getattr(team, "wellspring_pending", 0) + 1

def play_game(cfg, rng, drafters=None):
    if drafters is None: drafters = [True]*cfg.n_players
    gates = () if cfg.gate_counter <= 0 else ((4,) if cfg.single_gate else (3, 6))
    track = build_track(cfg.vault_scale, cfg.gate_counter, gates=gates)
    picks = (winchester_draft if cfg.draft_type=="winchester" else snake_draft)(cfg, rng, drafters)
    teams = [build_team(i, picks[i], cfg, rng) for i in range(cfg.n_players)]
    return run_engine(cfg, rng, teams, track)

def run_engine(cfg, rng, teams, track):
    for t in teams:
        t.trav_remaining = track[0].trav[0]; t.breach_remaining = track[0].breach
        if cfg.regroup:
            for _ in range(cfg.start_hand):
                if t.deck: t.hand.append(t.deck.pop())
        t.tiebreak = rng.random()
        t.wellspring_pending = 0
        t.breached_this_turn = False
        t.gps_pending = 0
        t.is_leader_now = False; t.ext_w_pen = 0; t.ext_s_pen = 0
        t.is_last_now = False; t.leader_gap = 0
    first_down_team = None; midpoint_leader = None; first_extractor = None; gemheart_taken = False; gemheart_destroyed = False
    init = list(range(len(teams))); rng.shuffle(init)
    leader_log = []
    eff_sum = {t.pid: [0.0]*5 for t in teams}; eff_cnt = {t.pid: 0 for t in teams}
    for rnd in range(cfg.max_rounds):
        init = init[1:] + init[:1]
        ldr = race_leader(teams)
        frontier = max((t.loc_idx for t in teams if t.finished_round is None), default=0)
        leader_log.append((ldr.pid if ldr is not None else None, frontier))
        last = race_last(teams)
        njam = sum(1 for o in teams if o is not ldr and o.finished_round is None
                   and any("eq_jammer" in g.tags for g in o.glads if not g.downed))
        nsap = sum(1 for o in teams if o is not ldr and o.finished_round is None
                   and any("eq_sapper" in g.tags for g in o.glads if not g.downed))
        for t in teams:
            t.is_leader_now = (ldr is not None and t is ldr)
            t.is_last_now = (last is not None and t is last)
            t.leader_gap = max(0, ldr.loc_idx - t.loc_idx) if (ldr is not None and t is not ldr) else 0
            t.ext_w_pen = 2*njam if t.is_leader_now else 0   # Jammer: -2 W to Leader per holder
            t.ext_s_pen = 2*nsap if t.is_leader_now else 0   # Sapper: -2 S to Leader per holder
        for t in teams:   # sample EFFECTIVE stats (base + temp + gear/leader-conditional) for calibration & effective-rho
            if t.finished_round is None:
                p = pooled(t, cfg, halfway(t), full=True)
                for i in range(5): eff_sum[t.pid][i] += p[i]
                eff_cnt[t.pid] += 1
        if cfg.blue_shell_prob > 0:
            active = [t for t in teams if t.finished_round is None]
            if len(active) >= 2:
                leader = max(active, key=lambda t: (t.loc_idx, -t.trav_remaining))
                trailer = min(active, key=lambda t: (t.loc_idx, -t.trav_remaining))
                if leader.loc_idx - trailer.loc_idx >= cfg.blue_shell_gap and rng.random() < cfg.blue_shell_prob:
                    leader.trav_remaining += cfg.blue_shell_knockback
        for t in teams:
            if t.finished_round is None:
                if cfg.enable_equip_abilities and not t.moved_this_turn and not getattr(t, "breached_this_turn", False) and any("idle_strain" in g.tags for g in t.glads if not g.downed):
                    if not (cfg.soften_drawbacks and rng.random() < 0.5):
                        deal_to_holder(t, "idle_strain", 1)
                t.moved_this_turn = False; t.healed_this_turn = False; t.breached_this_turn = False
                t.disrupted_this_turn = False; t.hack_intent = 0; t.braced = False
                t.attacked_this_turn = False; t.braced_this_turn = False; t.times_attacked = 0
                t.temp_mods = [0,0,0,0,0]
                for g in t.glads: g.dmg_round = 0
                if not cfg.enable_char_abilities:
                    for g in t.glads: g.endured = False
                draw_hand(t, cfg, rng)
                if getattr(t, "wellspring_pending", 0):
                    _draw_n(t, cfg, rng, t.wellspring_pending); t.wellspring_pending = 0
                if getattr(t, "gps_pending", 0):
                    _draw_n(t, cfg, rng, t.gps_pending); t.gps_pending = 0
                if cfg.enable_char_abilities and "live_off_land" in active_quirks(t) and not t.hand:
                    _draw_n(t, cfg, rng, 1)
                if cfg.enable_loadout_abilities and any("ld_salve" in g.tags for g in t.glads if not g.downed):
                    heal_team(t, 1, cfg)
                others = [o for o in teams if o is not t and o.finished_round is None]
                behind = any(o.loc_idx > t.loc_idx for o in others)
                if cfg.speed_draw_hook and behind and pooled(t, cfg, halfway(t))[S] >= cfg.speed_draw_threshold:
                    _draw_n(t, cfg, rng, 1)
                if cfg.catchup_draw and behind:
                    _draw_n(t, cfg, rng, cfg.catchup_draw)
                if cfg.leader_draw_pen and others and all(t.loc_idx >= o.loc_idx for o in others) \
                        and any(t.loc_idx > o.loc_idx for o in others):
                    for _ in range(cfg.leader_draw_pen):
                        if t.hand: t.discard.append(t.hand.pop())
        if cfg.rubberband:
            active = [t for t in teams if t.finished_round is None]
            if active:
                last = min(active, key=lambda t: (t.loc_idx, -t.trav_remaining))
                draw_hand(last, cfg, rng)
        stack = []
        if cfg.new_combat:
            chosen = {}
            for i in init:
                t = teams[i]
                if t.finished_round is not None: continue
                chosen[i] = choose_actions(t, teams, cfg, track, rng)
            for p in range(cfg.actions_per_turn):
                for i in init:
                    if i in chosen and p < len(chosen[i]):
                        stack.append((teams[i], chosen[i][p]))
        else:
            for i in init:
                t = teams[i]
                if t.finished_round is not None: continue
                for a in choose_actions(t, teams, cfg, track, rng): stack.append((t, a))
        for t, (atype, target) in reversed(stack):
            if t.finished_round is not None: continue
            if atype == "attack":
                if target is not None: target.times_attacked += 1
                resolve_attack(t, target, cfg, track, teams=teams)
                t.attacked_this_turn = True
                if first_down_team is None and target is not None and any_downed(target):
                    first_down_team = t.pid
            elif atype == "move": resolve_move(t, teams, cfg, track)
            elif atype == "breach": t.breached_this_turn = True; resolve_breach(t, teams, cfg, track, rng)
            elif atype == "heal": heal_team(t, 1, cfg)
            elif atype == "draw": _draw_n(t, cfg, rng, cfg.draw_card_amount)
            elif atype == "defend": t.braced = True; t.braced_this_turn = True
        if cfg.free_attack_per_turn:
            for i in init:
                t = teams[i]
                if t.finished_round is not None: continue
                for _ in range(cfg.free_attack_per_turn):
                    tgt = best_attack_target(t, teams, cfg, track)
                    if tgt is None: break
                    resolve_attack(t, tgt, cfg, track, teams=teams)
                    if first_down_team is None and any_downed(tgt):
                        first_down_team = t.pid
        for t in teams:
            if t.finished_round is not None: continue
            apply_hack(t, teams, cfg, track)
        for t in teams:
            if t.finished_round is not None: continue
            if track[t.loc_idx].effect == "heal": heal_team(t, 1, cfg)
            if team_wiped(t):
                t.finished_round = rnd; t.eliminated = True
                if cfg.vault_extract_counter > 0 and t.extracting:
                    gemheart_destroyed = True
                t.extracting = False; continue
            ethresh = cfg.vault_extract_counter if cfg.vault_extract_counter > 0 else cfg.extract_needed
            if t.extracting and t.extract_progress >= ethresh:
                t.won = True; t.finished_round = rnd
        if first_extractor is None:
            ex = [t for t in teams if t.extracting and t.finished_round is None]
            if ex: first_extractor = ex[0].pid
        if cfg.vault_extract_counter > 0 and any(t.extracting for t in teams):
            gemheart_taken = True
        if midpoint_leader is None:
            past = [t for t in teams if t.loc_idx > 4]
            if past: midpoint_leader = max(past, key=lambda t: t.loc_idx).pid
        won = [t for t in teams if t.won]
        if won:
            winner = max(won, key=lambda t: sum(g.hp for g in t.glads))
            return result(winner.pid, teams, midpoint_leader, first_down_team, rnd, cfg, first_extractor=first_extractor, leader_log=leader_log, eff=(eff_sum, eff_cnt))
        if gemheart_destroyed:
            return result(None, teams, midpoint_leader, first_down_team, rnd, cfg, leader_log=leader_log,
                          first_extractor=first_extractor, draw=True, eff=(eff_sum, eff_cnt))
        if all(t.finished_round is not None for t in teams): break
    active = [t for t in teams if not team_wiped(t)]
    if cfg.vault_extract_counter > 0 and gemheart_taken:
        return result(None, teams, midpoint_leader, first_down_team, cfg.max_rounds, cfg, leader_log=leader_log,
                      timeout=True, first_extractor=first_extractor, draw=True, eff=(eff_sum, eff_cnt))
    if active:
        w = max(active, key=lambda t: (t.extracting, t.loc_idx, -t.breach_remaining, sum(g.hp for g in t.glads)))
        return result(w.pid, teams, midpoint_leader, first_down_team, cfg.max_rounds, cfg, timeout=True, first_extractor=first_extractor, leader_log=leader_log, eff=(eff_sum, eff_cnt))
    return result(None, teams, midpoint_leader, first_down_team, cfg.max_rounds, cfg, timeout=True, first_extractor=first_extractor, leader_log=leader_log, eff=(eff_sum, eff_cnt))

def result(winner, teams, ml, fd, rounds, cfg, timeout=False, first_extractor=None, draw=False, leader_log=None, eff=None):
    eff_sum, eff_cnt = eff if eff else ({}, {})
    eff_stats = {t.pid: [eff_sum.get(t.pid, [0]*5)[i] / max(1, eff_cnt.get(t.pid, 0)) for i in range(5)]
                 for t in teams}
    # --- snowball metrics from the per-round (leader, frontier) log ---
    log = leader_log or []
    # lead-changes: collapse consecutive equal defined leaders over the whole race
    defined = [pid for (pid, floc) in log if pid is not None]
    collapsed = [p for i, p in enumerate(defined) if i == 0 or p != defined[i-1]]
    lead_changes = max(0, len(collapsed) - 1)
    first_leader = collapsed[0] if collapsed else None
    wire_to_wire = (1 if (winner is not None and first_leader is not None and winner == first_leader)
                    else (0 if (winner is not None and first_leader is not None) else None))
    # concentration over the CONTESTED window only (frontier past the start cluster,
    # before the final-vault lock-in), with no-leader/tie rounds kept in the denominator.
    WIN_START, WIN_END = 1, N_LOC - 1   # frontier loc in [1, 8) => locations 1..7
    window = [pid for (pid, floc) in log if WIN_START <= floc < WIN_END]
    wn = len(window)
    if wn > 0:
        cnt = {}
        for pid in window:
            if pid is not None: cnt[pid] = cnt.get(pid, 0) + 1
        lead_concentration = (max(cnt.values()) / wn) if cnt else 0.0
        winner_lead_share = (cnt.get(winner, 0) / wn) if winner is not None else None
        noleader_share = 1.0 - sum(cnt.values()) / wn
    else:
        lead_concentration = float('nan'); winner_lead_share = None; noleader_share = float('nan')
    return {
        "winner": winner, "midpoint_leader": ml, "first_down_team": fd, "draw": draw,
        "first_extractor": first_extractor, "rounds": rounds, "timeout": timeout,
        "lead_changes": lead_changes, "first_leader": first_leader,
        "wire_to_wire": wire_to_wire, "lead_concentration": lead_concentration,
        "winner_lead_share": winner_lead_share, "leader_defined_rounds": len(defined),
        "noleader_share": noleader_share, "window_rounds": wn,
        "eliminated_pids": [t.pid for t in teams if getattr(t, "eliminated", False)],
        "strengths": {t.pid: t.draft_score for t in teams},
        "wills": {t.pid: sum(g.base[W] for g in t.glads) for t in teams},
        "speeds": {t.pid: sum(g.base[S] for g in t.glads) for t in teams},
        "leths": {t.pid: sum(g.base[L] for g in t.glads) for t in teams},
        "mits":  {t.pid: sum(g.base[M] for g in t.glads) for t in teams},
        "eff_stats": eff_stats,   # per-team mean EFFECTIVE [L,M,S,V,W] over the game (for effective-rho + Phase-1 calibration)
        "progress": {t.pid: t.loc_idx + (1 if t.extracting else 0) for t in teams},
        "drafters": {t.pid: d for t, d in zip(teams, cfg_drafters(cfg, teams))},
    }
def cfg_drafters(cfg, teams): return [True]*len(teams)

def V5_CONFIG():
    """Locked V5 effects-on baseline. soften_drawbacks dropped (full frequency,
    equipment drawback damage routed to the holding gladiator)."""
    return Config(
        n_players=4, draft_type="winchester", new_combat=True, uncapped=True,
        slipstream_graduated=True, slipstream_bonus=3, gate_counter=5,
        gate_attack_prob=0.5, hack_disrupt="freeze", vault_extract_counter=0,
        draw_per_turn=1, hand_size=4, regroup=True, start_hand=4,
        first_entry_penalty=3, down_stagger=1, down_team_move_factor=0.5, ranged_forward_only=False, speed_breach_frac=0.5,
        enable_char_abilities=True, enable_loadout_abilities=True,
        enable_equip_abilities=True, soften_drawbacks=False,
    )

def run_config(cfg, n_games, seed=0, drafters=None):
    _YOMI["standoff"] = 0; _YOMI["multi"] = 0
    for k in _COMBAT: _COMBAT[k] = 0
    _TENSION["gn"].clear(); _TENSION["gf"].clear()
    rng = random.Random(seed)
    return summarize([play_game(cfg, rng, drafters) for _ in range(n_games)], cfg)

def summarize(results, cfg):
    n = len(results)
    valid = [r for r in results if r["winner"] is not None]
    timeouts = sum(1 for r in results if r["timeout"]) / n
    sv, wf, wv, spv, lv, mv = [], [], [], [], [], []
    for r in valid:
        for pid, s in r["strengths"].items():
            sv.append(s); wf.append(1 if r["winner"]==pid else 0)
            wv.append(r["wills"][pid]); spv.append(r["speeds"][pid])
            lv.append(r["leths"][pid]); mv.append(r["mits"][pid])
    rho_s = spearmanr(sv, wf).correlation if len(set(sv))>1 else float('nan')
    rho_w = spearmanr(wv, wf).correlation if len(set(wv))>1 else float('nan')
    rho_sp = spearmanr(spv, wf).correlation if len(set(spv))>1 else float('nan')
    rho_l = spearmanr(lv, wf).correlation if len(set(lv))>1 else float('nan')
    rho_m = spearmanr(mv, wf).correlation if len(set(mv))>1 else float('nan')
    # effective-stat rho: correlate mean EFFECTIVE (base+temp+gear/leader) stats with winning
    el, em, es, ev, ew, ewf = [], [], [], [], [], []
    for r in valid:
        for pid, vec in r.get("eff_stats", {}).items():
            el.append(vec[L]); em.append(vec[M]); es.append(vec[S]); ev.append(vec[V]); ew.append(vec[W])
            ewf.append(1 if r["winner"]==pid else 0)
    def _rho(xs):
        return spearmanr(xs, ewf).correlation if len(set(xs))>1 else float('nan')
    rho_l_eff, rho_m_eff, rho_s_eff, rho_v_eff, rho_w_eff = _rho(el), _rho(em), _rho(es), _rho(ev), _rho(ew)
    strong = sum(1 for r in valid if r["winner"]==max(r["strengths"], key=lambda p:r["strengths"][p]))
    strong_wr = strong/len(valid) if valid else float('nan')
    ml = [r for r in valid if r["midpoint_leader"] is not None]
    ml_wr = sum(1 for r in ml if r["winner"]==r["midpoint_leader"])/len(ml) if ml else float('nan')
    # --- new snowball framework ---
    w2w = [r["wire_to_wire"] for r in valid if r.get("wire_to_wire") is not None]
    wire_to_wire_wr = (sum(w2w)/len(w2w)) if w2w else float('nan')
    lc = [r["lead_changes"] for r in valid if r.get("leader_defined_rounds", 0) > 0]
    avg_lead_changes = (statistics.mean(lc)) if lc else float('nan')
    conc = [r["lead_concentration"] for r in valid if not (isinstance(r.get("lead_concentration"), float) and r["lead_concentration"]!=r["lead_concentration"])]
    mean_lead_concentration = (statistics.mean(conc)) if conc else float('nan')
    wls = [r["winner_lead_share"] for r in valid if r.get("winner_lead_share") is not None]
    mean_winner_lead_share = (statistics.mean(wls)) if wls else float('nan')
    nls = [r["noleader_share"] for r in valid if not (isinstance(r.get("noleader_share"), float) and r["noleader_share"]!=r["noleader_share"])]
    mean_noleader_share = (statistics.mean(nls)) if nls else float('nan')
    fd = [r for r in valid if r["first_down_team"] is not None]
    fd_wr = sum(1 for r in fd if r["winner"]==r["first_down_team"])/len(fd) if fd else float('nan')
    gaps = []
    for r in valid:
        pr = sorted(r["progress"].values(), reverse=True)
        if len(pr)>=2: gaps.append(pr[0]-pr[1])
    fe = [r for r in valid if r.get("first_extractor") is not None]
    fe_hold = sum(1 for r in fe if r["winner"]==r["first_extractor"])/len(fe) if fe else float('nan')
    yomi = (_YOMI["multi"]/_YOMI["standoff"]) if _YOMI["standoff"] else float('nan')
    return {
        "n_games": n, "timeout_rate": timeouts, "baseline_wr": 1.0/cfg.n_players,
        "strongest_wr": strong_wr, "rho_strength": rho_s, "rho_will": rho_w,
        "rho_speed": rho_sp, "rho_leth": rho_l, "rho_mit": rho_m,
        "rho_leth_eff": rho_l_eff, "rho_mit_eff": rho_m_eff, "rho_speed_eff": rho_s_eff,
        "rho_vit_eff": rho_v_eff, "rho_will_eff": rho_w_eff,
        "midleader_wr": ml_wr, "firstdown_wr": fd_wr,
        "wire_to_wire_wr": wire_to_wire_wr, "avg_lead_changes": avg_lead_changes,
        "lead_concentration": mean_lead_concentration, "winner_lead_share": mean_winner_lead_share,
        "noleader_share": mean_noleader_share,
        "extract_hold_wr": fe_hold,
        "yomi_richness": yomi,
        # NOTE: avg_gap is the FINAL 1st-vs-2nd margin (blowout vs nailbiter), NOT a snowball measure.
        "final_margin": statistics.mean(gaps) if gaps else float('nan'),
        "avg_gap": statistics.mean(gaps) if gaps else float('nan'),  # kept for back-compat; same as final_margin
        # NOTE: firstdown_wr is a single first-event snapshot (did first team to down an enemy win) -- tempo diagnostic only.
        "avg_rounds": statistics.mean([r["rounds"] for r in valid]) if valid else float('nan'),
    }

if __name__ == "__main__":
    PRUNED = {'RecoilHarness','StaticCloak','RedlineArray','Caltraps'}
    cfg = V5_CONFIG()
    out = run_config(cfg, 300, seed=1)
    print("Smoke test (locked V5 baseline, 300 games):")
    for k, v in out.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"  cap-alarm: {dict(_CAPALARM)}")
