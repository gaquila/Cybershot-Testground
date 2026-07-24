"""
standard_sim.py -- THE STANDARD SIM.
====================================
The canonical "full game, all layers on" battery for Cybershot V7. This is the
instrument any new card / tweak gets run through. One call, everything stacked:

    v7 canon  +  weights_v7  +  the 12-card Special Tactics core
    measured at 3p, 4p, 5p on the standard-9 track.

It handles all the install-order and layering correctness that bit us this arc:
  * v7.install() BEFORE special_harness (compose shim re-points the harness's
    import-time _orig_* refs at the live v7/weights functions so the harness
    chains ON TOP instead of reverting them).
  * specials are threaded into the v7 gear draft (v7 builds its own pool, so
    make_pool patching alone does NOT inject them).
  * engine left pristine on exit; V5_CONFIG stays bit-exact.

USAGE
-----
    import standard_sim as SS
    SS.run()                          # default 3/4/5p, std9, prints a table
    SS.run(players=(4,), n=2000)      # just 4p, more games
    SS.run(extra_specials=["ADV_newcard"])   # add a candidate card to the core
    SS.run(track="short7")            # the shorter track

    df = SS.battery()                 # returns the raw dict for programmatic use

DESIGNING A NEW CARD: add its code+spec to special_harness.SPECIAL_CARDS, then
    SS.run(extra_specials=["ADV_yourcard"])
and compare against SS.run() (core only). If length/timeout/snowball hold, it's
sim-safe; if it's a heal/defend/timing/attack card, treat weak numbers as
UNMEASURED (bot-blind), not bad -- carry to physical playtest.
"""
import random
import statistics

import cybershot_sim as C
import v7
import weights_v7 as WT
import special_harness as H
import compose

C.PRUNED = {'RecoilHarness', 'StaticCloak', 'RedlineArray', 'Caltraps'}

# The approved 12-card Special Tactics core = all V6_SET cards that are NOT
# attack-tagged. The 5 attack cards are playtest-only "bot-blind keepers".
ATTACK_CARDS = {c for c in H.V6_SET
                if "attack" in (H.SPECIAL_CARDS.get(c, {}).get("want") or ())}
CORE_12 = sorted(c for c in H.V6_SET if c not in ATTACK_CARDS)

METRICS = ("avg_rounds", "timeout_rate", "avg_lead_changes", "lead_concentration",
           "strongest_wr", "baseline_wr", "midleader_wr", "firstdown_wr",
           "wire_to_wire_wr", "rho_mit_eff", "rho_speed_eff", "rho_leth_eff",
           "rho_will_eff")

SEEDS = (1, 2, 3)


def _cfg(track, n):
    from dataclasses import replace
    return replace(v7.V7_CANON(track), n_players=n)


def _pace(games):
    """The PACE TRIPLE + tail: typical length that is NOT contaminated by the
    100-round deadlock tail, reported alongside the non-finish rate so the two
    are never read apart. avg_rounds smears timeouts (each a flat max_rounds)
    into the mean; median/finisher_mean do not. Excluding timeouts from a lone
    length number is the opposite trap (more deadlocks -> looks shorter), so
    timeout_rate/p90 travel WITH them."""
    rounds = [g["rounds"] for g in games]
    fin = [g["rounds"] for g in games if not g["timeout"]]
    rs = sorted(rounds)
    return {
        "median_rounds": statistics.median(rounds),
        "finisher_mean": statistics.mean(fin) if fin else float("nan"),
        "p90_rounds": rs[min(len(rs) - 1, int(0.90 * len(rs)))],
    }


_PACE_KEYS = ("median_rounds", "finisher_mean", "p90_rounds")


def _measure(track, n, pool, seeds, ngames):
    cfg = _cfg(track, n)
    active = pool is not None and len(pool) > 0
    if active:
        compose.install_harness_over_live()
        compose.enable_specials_in_v7_draft()
        H.HS.pool_enabled = set(pool)
        H.HS.pool_copies = 1
        H.HS.max_specials = 2
    S = []
    P = []
    for s in seeds:
        rng = random.Random(s)
        games = [C.play_game(cfg, rng) for _ in range(ngames)]
        S.append(C.summarize(games, cfg))
        P.append(_pace(games))
    if active:
        compose.disable_specials_in_v7_draft()
        compose.uninstall_harness()
    out = {k: statistics.mean(x[k] for x in S) for k in METRICS}
    for k in _PACE_KEYS:
        out[k] = statistics.mean(x[k] for x in P)
    return out


def battery(players=(3, 4, 5), track="standard9", n=1000, seeds=SEEDS,
            specials=True, extra_specials=None):
    """Return {n_players: metrics-dict}. specials=True uses the 12-card core;
    extra_specials adds candidate card codes on top of the core."""
    pool = None
    if specials:
        pool = list(CORE_12) + list(extra_specials or [])
    v7.install(); WT.install()
    out = {}
    for p in players:
        out[p] = _measure(track, p, pool, seeds, n)
    WT.uninstall(); v7.uninstall()
    return out


def run(players=(3, 4, 5), track="standard9", n=1000, seeds=SEEDS,
        specials=True, extra_specials=None):
    """Run the Standard Sim and print the canonical table."""
    res = battery(players, track, n, seeds, specials, extra_specials)
    layer = "12-card core" + (f" + {extra_specials}" if extra_specials else "") \
        if specials else "NO specials"
    print("=" * 96)
    print(f"STANDARD SIM  --  V7 canon + weights + [{layer}]  --  {track}, "
          f"{len(seeds)}x{n} games")
    print("=" * 96)
    # PACE TRIPLE first (median/finisher-mean = typical length, uncontaminated),
    # then the non-finish tail (t/out, p90) that MUST be read alongside them,
    # then avg_rounds kept for continuity with prior-arc numbers.
    print(f"{'players':<9}{'medRnd':>8}{'finAvg':>8}{'t/out':>8}{'p90':>6}"
          f"{'avgRnd':>8}{'leadCh':>8}{'conc':>8}{'strWR':>8}{'lift':>7}")
    for p in sorted(res):
        r = res[p]
        print(f"{p:<9}{r['median_rounds']:>8.1f}{r['finisher_mean']:>8.1f}"
              f"{r['timeout_rate']:>8.3f}{r['p90_rounds']:>6.0f}"
              f"{r['avg_rounds']:>8.1f}{r['avg_lead_changes']:>8.2f}"
              f"{r['lead_concentration']:>8.3f}{r['strongest_wr']:>8.3f}"
              f"{r['strongest_wr']/r['baseline_wr']:>7.2f}")
    print(f"\n{'players':<9}{'rhoMit':>8}{'rhoSpd':>8}{'rhoLeth':>8}{'rhoWill':>8}")
    for p in sorted(res):
        r = res[p]
        print(f"{p:<9}{r['rho_mit_eff']:>8.3f}{r['rho_speed_eff']:>8.3f}"
              f"{r['rho_leth_eff']:>8.3f}{r['rho_will_eff']:>8.3f}")
    return res


if __name__ == "__main__":
    run()
