"""
ARCHETYPE VIABILITY TEST  (v2 -- effect-aware, drafted)
======================================================
Unlike the old fixed-stat-line harness, this DRAFTS each archetype team toward
its target stat(s) from the shared Winchester pool WITH EFFECTS ON, so loadout /
equipment / character / leader-conditional effects are all in play. One archetype
specialist is pitted against three balanced (calibrated-greedy) opponents.

Each archetype is built at three intensities -- mild / moderate / extreme -- by
adding a stat-bias bonus of increasing strength on top of the engine's real
card_value (so all normal draft logic is preserved, just tilted).

Runs on the calibrated STAT_WEIGHTS and reports the new metric framework:
archetype win-rate (vs 0.25 baseline) plus snowball reads for the matchup.
"""
import random, statistics
import cybershot_sim as C
from cybershot_sim import (Config, make_pool, card_value, build_team, run_engine,
                           build_track, CHARACTERS, LOADOUTS, EQUIPMENT,
                           L, M, S, V, W)

C.PRUNED = {'RecoilHarness', 'StaticCloak', 'RedlineArray', 'Caltraps'}

ARCHETYPES = {
    "Hacker":   [W],
    "Cannon":   [L],
    "Speed":    [S],
    "Fortress": [M, V],
}
INTENSITY = {"mild": 5.0, "moderate": 15.0, "extreme": 45.0}


def V5():
    return Config(
        n_players=4, draft_type="winchester", new_combat=True, uncapped=True,
        slipstream_graduated=True, slipstream_bonus=3, gate_counter=5,
        gate_attack_prob=0.5, hack_disrupt="freeze", vault_extract_counter=0,
        draw_per_turn=1, hand_size=4, regroup=True, start_hand=4,
        first_entry_penalty=3, down_stagger=1, down_team_move_factor=0.5, ranged_forward_only=False,
        enable_char_abilities=True, enable_loadout_abilities=True,
        enable_equip_abilities=True, soften_drawbacks=False,
    )


def biased_value(have, card, cfg, bias_stats, strength):
    base = card_value(have, card, cfg)
    if card["kind"] == "loadout":
        # loadouts store the stat INDICES they boost (each by cfg.loadout_bonus)
        idxs = LOADOUTS[card["name"]][0]
        contrib = sum(cfg.loadout_bonus for idx in idxs if idx in bias_stats)
    else:
        stats = CHARACTERS[card["name"]][0] if card["kind"] == "char" else EQUIPMENT[card["name"]][0]
        contrib = sum(stats[i] for i in bias_stats)
    return base + strength * contrib


def biased_winchester(cfg, rng, bias_list):
    pool = make_pool(rng); n = cfg.n_players
    picks = [[] for _ in range(n)]
    for _ in range(2):
        hands = [[pool.pop() for _ in range(12)] for _ in range(n)]
        for k in range(n + 1):
            for i in range(n):
                hand = hands[(i - k) % n]
                if len(hand) > 2:
                    if bias_list[i] is None:
                        take = sorted(hand, key=lambda c: -card_value(picks[i], c, cfg))[:2]
                    else:
                        bs, strg = bias_list[i]
                        take = sorted(hand, key=lambda c: -biased_value(picks[i], c, cfg, bs, strg))[:2]
                    for c in take:
                        hand.remove(c); picks[i].append(c)
                elif len(hand) == 2:
                    hand.clear()
    return picks


def run_matchup(cfg, bias_list, n_games, seed=1234):
    rng = random.Random(seed)
    wins = [0] * cfg.n_players; to = 0; rounds = []
    lead_changes = []; concentration = []
    gates = () if cfg.gate_counter <= 0 else (3, 6)
    for _ in range(n_games):
        track = build_track(cfg.vault_scale, cfg.gate_counter, gates=gates)
        picks = biased_winchester(cfg, rng, bias_list)
        teams = [build_team(i, picks[i], cfg, rng) for i in range(cfg.n_players)]
        res = run_engine(cfg, rng, teams, track)
        if res["winner"] is not None:
            wins[res["winner"]] += 1
        if res["timeout"]: to += 1
        rounds.append(res["rounds"])
        if res.get("lead_changes") is not None: lead_changes.append(res["lead_changes"])
        lc = res.get("lead_concentration")
        if isinstance(lc, float) and lc == lc: concentration.append(lc)
    n = n_games
    return {
        "arch_wr": wins[0] / n,
        "bal_wr": statistics.mean([wins[i] / n for i in range(1, cfg.n_players)]),
        "timeout": to / n,
        "rounds": statistics.mean(rounds),
        "lead_changes": statistics.mean(lead_changes) if lead_changes else float('nan'),
        "concentration": statistics.mean(concentration) if concentration else float('nan'),
    }


if __name__ == "__main__":
    NG = 1200
    print("=" * 84)
    print(f"ARCHETYPE VIABILITY (drafted, effects ON, calibrated weights) - {NG} games/matchup")
    print("1 specialist vs 3 balanced. baseline 0.250.  healthy 0.22-0.40 | >0.45 dominant | <0.15 punished")
    print("=" * 84)
    cfg = V5()
    ctrl = run_matchup(cfg, [None] * 4, NG, seed=1000)
    print(f"\n{'Balanced (control)':<22}{ctrl['arch_wr']:>8.1%}  (bal avg {ctrl['bal_wr']:.1%}, "
          f"ldChg {ctrl['lead_changes']:.2f}, conc {ctrl['concentration']:.3f}, "
          f"to {ctrl['timeout']:.1%}, rnds {ctrl['rounds']:.0f})")
    for arch, bstats in ARCHETYPES.items():
        print()
        for lvl, strg in INTENSITY.items():
            bias_list = [(bstats, strg), None, None, None]
            m = run_matchup(cfg, bias_list, NG, seed=2000)
            tag = ""
            if m["arch_wr"] > 0.45: tag = " <-- DOMINANT"
            elif m["arch_wr"] < 0.15: tag = " <-- punished"
            print(f"{arch + '-' + lvl:<22}{m['arch_wr']:>8.1%}  (bal avg {m['bal_wr']:.1%}, "
                  f"ldChg {m['lead_changes']:.2f}, conc {m['concentration']:.3f}, "
                  f"to {m['timeout']:.1%}, rnds {m['rounds']:.0f}){tag}")
