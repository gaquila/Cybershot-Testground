"""
archetype_v7.py -- archetype viability on the V7 two-part draft.
================================================================
archetype_v6.biased_winchester uses the OLD single-pool winchester, which
fields only ~2.85 gladiators -- the same bug v7.py fixed for the main draft.
This module runs the archetype test through a biased version of the V7 draft
(mini-winchester characters -> exactly 4, then biased gear winchester), so
archetype teams are real 4-gladiator teams.

Install v7 + weights_v7 first. Balanced drafters use the (patched) card_value;
the archetype team uses biased_value tilted toward its stat.

bias_list[i] is None for a balanced drafter, or (stat_idxs, strength) for the
archetype seat. The archetype team is ROTATED across seats to cancel the
~±3pp structural seat bias, exactly like the weight calibrator.
"""
import random
import statistics

import cybershot_sim as C
import v7
from archetype_v6 import biased_value, ARCHETYPES, INTENSITY


def _biased_pick(have, avail, k, rng, bias, cfg):
    if bias is None:
        return sorted(avail, key=lambda c: -C.card_value(have, c, cfg))[:k]
    bs, strg = bias
    return sorted(avail, key=lambda c: -biased_value(have, c, cfg, bs, strg))[:k]


def biased_v7_draft(cfg, rng, bias_list):
    """V7 two-part draft with per-seat stat bias. Guarantees 4 gladiators."""
    n = cfg.n_players
    picks = [[] for _ in range(n)]

    # ---- characters: mini-winchester (hands of 4, take 1, pass) -> 4 each ----
    chars = v7._char_pool(rng, n)
    hands = [[chars.pop() for _ in range(4)] for _ in range(n)]
    for kk in range(4):
        for i in range(n):
            hand = hands[(i - kk) % n]
            if hand:
                c = _biased_pick(picks[i], hand, 1, rng, bias_list[i], cfg)[0]
                hand.remove(c)
                picks[i].append(c)

    # ---- gear winchester (same structure as v7_draft) ----
    hs = v7.LEVERS["gear_hand_size"]
    passes = (hs - 2) // 2
    gear = v7._gear_pool(rng, n, hs)
    for _ in range(2):
        hands = [[gear.pop() for _ in range(hs)] for _ in range(n)]
        for kk in range(passes):
            for i in range(n):
                hand = hands[(i - kk) % n]
                if len(hand) > 2:
                    take = _biased_pick(picks[i], hand, 2, rng, bias_list[i], cfg)
                    for c in take:
                        hand.remove(c)
                        picks[i].append(c)
        for h in hands:
            h.clear()
    return picks


def run_archetype(cfg, bias, n_games, seed=1234):
    """1 archetype seat vs (n-1) balanced, rotated across all seats."""
    rng = random.Random(seed)
    n = cfg.n_players
    per = max(1, n_games // n)
    total = per * n
    wins = 0
    rounds = []
    for seat in range(n):
        bias_list = [None] * n
        bias_list[seat] = bias
        for _ in range(per):
            track = C.build_track(cfg.vault_scale, cfg.gate_counter, gates=(3, 6),
                                  vault_breach=cfg.vault_breach, layout=cfg.track_layout)
            C.ABILITY_CAP_ON = cfg.ability_cap
            C.N_LOC = len(track)
            picks = biased_v7_draft(cfg, rng, bias_list)
            teams = [C.build_team(i, picks[i], cfg, rng) for i in range(n)]
            res = C.run_engine(cfg, rng, teams, track)
            if res["winner"] == seat:
                wins += 1
            rounds.append(res["rounds"])
    return {"arch_wr": wins / total, "baseline": 1.0 / n,
            "rounds": statistics.mean(rounds)}
