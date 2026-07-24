"""
archetype_v6.py -- V6-correct archetype viability harness.
==========================================================
WHY: archetype_test.py has three latent V5-isms that make it unable to measure
V6, even if handed V6_CONFIG:

  1. It defines its own local V5() config (a byte-copy of V5_CONFIG()).
  2. It calls build_track(vault_scale, gate_counter, gates=gates) WITHOUT
     vault_breach= or layout=, so V6's vault_breach=20 / short7 are ignored.
  3. It bypasses play_game(), which is the ONLY place that sets the module
     globals ABILITY_CAP_ON (from cfg.ability_cap) and N_LOC (from len(track)).
     So V6's "ability cap removed" never applies (ABILITY_CAP_ON stays True),
     and N_LOC stays 9 (wrong for short7 -> mis-detects the Final Vault).

This module fixes all three and keeps a bit-exact V5 regression mode so we can
prove the rewrite is faithful before trusting its V6 output.
"""
import random
import statistics

import cybershot_sim as C
from cybershot_sim import L, M, S, V, W

C.PRUNED = {'RecoilHarness', 'StaticCloak', 'RedlineArray', 'Caltraps'}

ARCHETYPES = {"Hacker": [W], "Cannon": [L], "Speed": [S], "Fortress": [M, V]}
# V7 rescale. Old {5,15,45} were fitted before weights_v7 compressed the gear
# card_value spread (~10-30). The bias term is strength*stat_contrib and is
# ADDED to card_value, so at 45 a 3-point stat adds 135 and the archetype
# drafter picks purely by bias stat, ignoring quality -> every archetype looks
# non-viable (measurement artifact). Rescaled so the bias tilts picks without
# erasing quality: at extreme=3.0 a 3-point stat adds ~9 (comparable to spread).
# Validated: reproduces the step-5 picture (Fortress strongest ~0.33 WR / lift
# ~1.26, extremes taxed, Speed weakest). Install v7+weights_v7 before measuring.
INTENSITY = {"mild": 0.6, "moderate": 1.5, "extreme": 3.0}


def biased_value(have, card, cfg, bias_stats, strength):
    """card_value tilted toward bias_stats. Specials have no stat line -> passthrough."""
    base = C.card_value(have, card, cfg)
    kind = card["kind"]
    if kind == "special":                      # harness-injected Special Tactics
        return base
    if kind == "loadout":
        idxs = C.LOADOUTS[card["name"]][0]
        contrib = sum(cfg.loadout_bonus for idx in idxs if idx in bias_stats)
    else:
        table = C.CHARACTERS if kind == "char" else C.EQUIPMENT
        stats = table[card["name"]][0]
        contrib = sum(stats[i] for i in bias_stats)
    return base + strength * contrib


def biased_winchester(cfg, rng, bias_list):
    pool = C.make_pool(rng)
    n = cfg.n_players
    picks = [[] for _ in range(n)]
    for _ in range(2):
        hands = [[pool.pop() for _ in range(12)] for _ in range(n)]
        for k in range(n + 1):
            for i in range(n):
                hand = hands[(i - k) % n]
                if len(hand) > 2:
                    if bias_list[i] is None:
                        take = sorted(hand, key=lambda c: -C.card_value(picks[i], c, cfg))[:2]
                    else:
                        bs, strg = bias_list[i]
                        take = sorted(hand, key=lambda c: -biased_value(picks[i], c, cfg, bs, strg))[:2]
                    for c in take:
                        hand.remove(c)
                        picks[i].append(c)
                elif len(hand) == 2:
                    hand.clear()
    return picks


def run_matchup(cfg, bias_list, n_games, seed=1234, legacy_track=False):
    """legacy_track=True reproduces archetype_test.py's V5 build_track call exactly."""
    rng = random.Random(seed)
    wins = [0] * cfg.n_players
    to = 0
    rounds, lead_changes, concentration = [], [], []
    gates = () if cfg.gate_counter <= 0 else (3, 6)

    for _ in range(n_games):
        if legacy_track:
            track = C.build_track(cfg.vault_scale, cfg.gate_counter, gates=gates)
        else:
            # V6: honour vault_breach + track_layout, exactly as play_game does
            track = C.build_track(cfg.vault_scale, cfg.gate_counter, gates=gates,
                                  vault_breach=cfg.vault_breach, layout=cfg.track_layout)
        # CRITICAL: play_game normally sets these globals; we bypass it, so set them here.
        C.ABILITY_CAP_ON = cfg.ability_cap
        C.N_LOC = len(track)

        picks = biased_winchester(cfg, rng, bias_list)
        teams = [C.build_team(i, picks[i], cfg, rng) for i in range(cfg.n_players)]
        res = C.run_engine(cfg, rng, teams, track)

        if res["winner"] is not None:
            wins[res["winner"]] += 1
        if res["timeout"]:
            to += 1
        rounds.append(res["rounds"])
        if res.get("lead_changes") is not None:
            lead_changes.append(res["lead_changes"])
        lc = res.get("lead_concentration")
        if isinstance(lc, float) and lc == lc:
            concentration.append(lc)

    n = n_games
    return {
        "arch_wr": wins[0] / n,
        "bal_wr": statistics.mean([wins[i] / n for i in range(1, cfg.n_players)]),
        "timeout": to / n,
        "rounds": statistics.mean(rounds),
        "lead_changes": statistics.mean(lead_changes) if lead_changes else float('nan'),
        "concentration": statistics.mean(concentration) if concentration else float('nan'),
    }


def legacy_v5_mode(cfg=None):
    """Reproduce archetype_test.py's exact conditions for the regression guard."""
    C.ABILITY_CAP_ON = True   # module default the old harness silently relied on
    C.N_LOC = 9
    return cfg or C.V5_CONFIG()
