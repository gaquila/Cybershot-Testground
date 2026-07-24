"""
v8_cards.py -- V8 candidate content harness (new characters / gear / tactics).
=============================================================================
Adds George's + Claude's approved V8 cards ON TOP of the pristine engine, the
same way every other layer works: monkey-patch on install(), restore on
uninstall(), bit-exact inert when not installed.

INSTALL ORDER: v7.install(); weights_v7.install(); v8_cards.install(); then
compose the special_harness OVER the live (v8-wrapped) functions. So install
v8 AFTER v7+weights but BEFORE compose.install_harness_over_live(), and
uninstall in reverse. (See v8_battery.py for the canonical stack.)

SCREENABILITY (what the greedy bot can actually measure):
  Wired & screenable ....... Feratu, Jayred(saboteur), Sephira, Vulturus, Baal,
                             Trailblazer, Bloodletter, PowerCord, PanicShield,
                             OverdriveCell, ADV_aegis, ADV_secondwind,
                             ADV_establish, ADV_gambit(draw residue)
  Stat-body only (bot-blind reactive/info) ... Stephenos(Martyr), Finch(Scout),
                             Enigma, Pythia(Seer)  -- drafted as real bodies,
                             abilities are PLAYTEST-ONLY, not modeled.
  Approximations flagged inline with #APPROX.
"""
from collections import Counter
import cybershot_sim as C
from cybershot_sim import L, M, S, V, W
from cybershot_sim import active_quirks, add_temp, heal_team

# fire-counters (diagnostic only; DEBUG stays False in normal runs -> zero cost)
DEBUG = False
_COUNTS = Counter()
def _bump(k):
    if DEBUG:
        _COUNTS[k] += 1

# ------------------------------------------------------------------ CONTENT
# characters: name -> ([L,M,S,V,W], quirk_tag)
NEW_CHARACTERS = {
    "Feratu":    ([2, 0, 3, 1, 0], "feratu"),      # lifesteal on attack
    "Sephira":   ([2, 2, 0, 3, 0], "sephira"),     # on enemy entry: -2L/-2M + discard
    "Vulturus":  ([2, 0, 1, 2, 2], "vulturus"),    # draw 2 when you down a glad
    "Baal":      ([3, 0, 2, 2, 0], "baal"),        # +2 L vs teams with a downed glad  #APPROX: George wrote "V3,M0,S2,V2,W0"; read as L3 (typo)
    # stat-body only (abilities are playtest-only / bot-blind):
    "Stephenos": ([0, 2, 1, 2, 2], "v8_martyr"),   # Martyr (reactive self-sac) -- not modeled
    "Finch":     ([1, 2, 2, 1, 1], "v8_scout"),    # Scout (info) -- not modeled
    "Enigma":    ([1, 0, 0, 3, 3], "v8_enigma"),   # regroup->reorder -- not modeled
    "Pythia":    ([0, 1, 1, 2, 3], "v8_seer"),     # stack peek -- not modeled
}
# Jayred is RE-QUIRKED from night_thief -> saboteur (discard 1). Stats unchanged.
JAYRED_NEW_QUIRK = "saboteur"

# loadouts: name -> ([stat_idxs +2 each], tag, range_tag)
NEW_LOADOUTS = {
    "Trailblazer": ([S, V], "ld_trailblazer", None),   # draw on entering a location
    "Bloodletter": ([L, V], "ld_bloodletter", "melee"),# heal 1 on melee damage dealt
}
# equipment: name -> ([L,M,S,V,W flat], tag)
NEW_EQUIPMENT = {
    "PowerCord":     ([0, 0, 0, 0, 0], "eq_powercord"),   # +max(0,5-loc) to holder's top stat
    "PanicShield":   ([0, 0, 0, 0, 0], "eq_panicshield"), # on being downed: +2 M + brace
    "OverdriveCell": ([0, 0, 0, 0, 0], "eq_overdrive"),   # +1 all while undamaged this race
}
# draft valuation for new tags (added to EFFECT_VALUE; 0.0 for unmodeled bodies)
NEW_EFFECT_VALUES = {
    "feratu": 2.0, "saboteur": 1.0, "sephira": 1.5, "vulturus": 1.5, "baal": 1.0,
    "v8_martyr": 0.0, "v8_scout": 0.0, "v8_enigma": 0.0, "v8_seer": 0.0,
    "ld_trailblazer": 2.0, "ld_bloodletter": 2.0,
    "eq_powercord": 1.5, "eq_panicshield": 1.0, "eq_overdrive": 1.5,
}
# new Special Tactics (declarative; bot-blind parts flagged n/m = not modeled)
NEW_SPECIALS = {
    "ADV_aegis":      dict(name="Aegis Field",   tier="advanced", want=("defend", "heal"),
                           buff=(M, 2), heal=1, draw=0, acts=["defend"],
                           job="shield(#APPROX=+2M)/heal", complex=False),
    "ADV_secondwind": dict(name="Second Wind",   tier="advanced", want=("heal", "draw"),
                           heal_each=2, draw=1, noprimary=True,
                           job="revive(#APPROX heal_each)/econ; speed-cost n/m", complex=True),
    "ADV_establish":  dict(name="Establish Order", tier="advanced", want=("draw", "heal"),
                           heal=2, draw=2, noprimary=True,
                           job="econ/sustain; stack-reorder n/m", complex=True),
    "ADV_measure":    dict(name="Measure/Measure", tier="advanced", want=("defend", "attack"),
                           buff=(M, 2), heal=0, draw=0, acts=["defend"],
                           job="reactive branch n/m", complex=True),
    "ADV_sowchaos":   dict(name="Sow Chaos",     tier="advanced", want=("attack",),
                           buff=None, heal=0, draw=1, acts=["attack"],
                           job="discard+reorder n/m; 1 direct approx as attack", complex=True),
    "ADV_gambit":     dict(name="Gambit",        tier="advanced", want=("draw",),
                           draw=2, noprimary=True,
                           job="stack-shuffle n/m + draw", complex=True),
}

_installed = False
_saved = {}
_orig_char_quirk = None


# ------------------------------------------------------------------ WRAPPERS
def _wrap_compute_attack(orig):
    def _f(team, target, cfg, track):
        val = orig(team, target, cfg, track)
        if cfg.enable_char_abilities and target is not None and "baal" in active_quirks(team):
            if any(g.downed for g in target.glads):
                val += 2; _bump("baal")   # Executioner/Baal: +2 L vs teams with a downed gladiator
        return val
    return _f


def _wrap_resolve_attack(orig):
    def _f(team, target, cfg, track, teams=None):
        dbefore = sum(g.dmg_total for g in target.glads) if target is not None else 0
        downs_before = sum(1 for g in target.glads if g.downed) if target is not None else 0
        out = orig(team, target, cfg, track, teams=teams)
        if target is not None:
            dmg = sum(g.dmg_total for g in target.glads) - dbefore   # robust to return type
            if dmg > 0 and cfg.enable_char_abilities and "feratu" in active_quirks(team):
                heal_team(team, int(dmg), cfg); _bump("feratu")   # Feratu lifesteal #APPROX: team heal, revive-first
            if dmg > 0 and cfg.enable_loadout_abilities \
                    and (target.loc_idx - team.loc_idx) == 0 \
                    and any("ld_bloodletter" in g.tags for g in team.glads if not g.downed):
                heal_team(team, 1, cfg); _bump("bloodletter")     # Bloodletter: heal 1 on melee damage
            if cfg.enable_char_abilities and "vulturus" in active_quirks(team):
                if sum(1 for g in target.glads if g.downed) > downs_before:
                    team.gps_pending = getattr(team, "gps_pending", 0) + 2; _bump("vulturus")  # Vulturus draw 2 on down
        return out
    return _f


def _wrap_allocate_damage(orig):
    def _f(target, dmg):
        downs_before = sum(1 for g in target.glads if g.downed)
        r = orig(target, dmg)
        if sum(1 for g in target.glads if g.downed) > downs_before \
                and any("eq_panicshield" in g.tags for g in target.glads if not g.downed):
            add_temp(target, M, 2, "panicshield"); target.braced = True; _bump("panicshield")   # Panic Shield
        return r
    return _f


def _wrap_advance(orig):
    def _f(team, teams, cfg, track):
        prev = team.loc_idx
        orig(team, teams, cfg, track)
        if team.loc_idx == prev:
            return
        if cfg.enable_loadout_abilities and any("ld_trailblazer" in g.tags for g in team.glads if not g.downed):
            team.gps_pending = getattr(team, "gps_pending", 0) + 1; _bump("trailblazer")   # Trailblazer draw
        if cfg.enable_char_abilities:
            for o in teams:                                          # Sephira: enemy entering her loc
                if o is team or o.finished_round is not None:
                    continue
                if o.loc_idx == team.loc_idx and "sephira" in active_quirks(o):
                    add_temp(team, L, -2, "sephira"); add_temp(team, M, -2, "sephira"); _bump("sephira")
                    if team.hand:
                        team.discard.append(team.hand.pop())
                    break
            for o in teams:                                          # Saboteur/Jayred: traversal resolved in her loc
                if o is team or o.finished_round is not None:
                    continue
                if o.loc_idx == prev and "saboteur" in active_quirks(o):
                    if team.hand:
                        team.discard.append(team.hand.pop()); _bump("saboteur")
                    break
    return _f


def _wrap_resolve_breach(orig):
    def _f(team, teams, cfg, track, rng=None):
        before_b = team.breach_remaining
        r = orig(team, teams, cfg, track, rng=rng)
        if cfg.enable_char_abilities and before_b > 0 and team.breach_remaining <= 0:
            for o in teams:                                          # Saboteur: breach resolved in her loc
                if o is team or o.finished_round is not None:
                    continue
                if o.loc_idx == team.loc_idx and "saboteur" in active_quirks(o):
                    if team.hand:
                        team.discard.append(team.hand.pop())
                    break
        return r
    return _f


def _wrap_gear_temp(orig):
    def _f(team, cfg, track):
        m = orig(team, cfg, track)
        if not cfg.enable_equip_abilities:
            return m
        if any("eq_overdrive" in g.tags for g in team.glads if not g.downed):
            undamaged = all(g.dmg_total == 0 for g in team.glads) and not any(g.downed for g in team.glads)
            if undamaged:
                for i in range(5):
                    m[i] += 1                     # Overdrive Cell: +1 all while flawless
                _bump("overdrive")
        for g in team.glads:
            if g.downed or "eq_powercord" not in g.tags:
                continue
            val = max(0, 5 - team.loc_idx)         # Power Cord: front-loaded, decays with distance
            if val:
                hi = max(range(5), key=lambda i: g.base[i])   # #APPROX: put it on the holder's top stat
                m[hi] += val; _bump("powercord")
        return m
    return _f


_WRAPS = {
    "compute_attack": _wrap_compute_attack,
    "resolve_attack": _wrap_resolve_attack,
    "allocate_damage": _wrap_allocate_damage,
    "advance": _wrap_advance,
    "resolve_breach": _wrap_resolve_breach,
    "gear_temp": _wrap_gear_temp,
}


# ------------------------------------------------------------------ INSTALL
def install():
    global _installed, _orig_char_quirk
    if _installed:
        return
    # 1. content
    for nm, spec in NEW_CHARACTERS.items():
        C.CHARACTERS[nm] = (list(spec[0]), spec[1])
    _orig_char_quirk = C.CHARACTERS["Jayred"][1]
    C.CHARACTERS["Jayred"] = (list(C.CHARACTERS["Jayred"][0]), JAYRED_NEW_QUIRK)
    for nm, spec in NEW_LOADOUTS.items():
        C.LOADOUTS[nm] = (list(spec[0]), spec[1], spec[2])
    for nm, spec in NEW_EQUIPMENT.items():
        C.EQUIPMENT[nm] = (list(spec[0]), spec[1])
    C.EFFECT_VALUE.update(NEW_EFFECT_VALUES)
    # register new tactics in the special harness (if loaded)
    try:
        import special_harness as H
        for code, spec in NEW_SPECIALS.items():
            H.SPECIAL_CARDS[code] = dict(spec)
    except Exception:
        pass
    # 2. wrappers (capture whatever is LIVE now so we chain on top of v7/weights)
    for name, mk in _WRAPS.items():
        _saved[name] = getattr(C, name)
        setattr(C, name, mk(_saved[name]))
    _installed = True


def uninstall():
    global _installed, _orig_char_quirk
    if not _installed:
        return
    for name, orig in _saved.items():
        setattr(C, name, orig)
    _saved.clear()
    for nm in NEW_CHARACTERS:
        C.CHARACTERS.pop(nm, None)
    if _orig_char_quirk is not None:
        C.CHARACTERS["Jayred"] = (list(C.CHARACTERS["Jayred"][0]), _orig_char_quirk)
        _orig_char_quirk = None
    for nm in NEW_LOADOUTS:
        C.LOADOUTS.pop(nm, None)
    for nm in NEW_EQUIPMENT:
        C.EQUIPMENT.pop(nm, None)
    for tag in NEW_EFFECT_VALUES:
        C.EFFECT_VALUE.pop(tag, None)
    try:
        import special_harness as H
        for code in NEW_SPECIALS:
            H.SPECIAL_CARDS.pop(code, None)
    except Exception:
        pass
    _installed = False


ALL_NEW_TACTICS = list(NEW_SPECIALS)
NEW_CHAR_NAMES = list(NEW_CHARACTERS)
