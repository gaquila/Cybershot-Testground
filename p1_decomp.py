"""
p1_decomp.py -- Phase-1 length-tax decomposition (record of finding).
=====================================================================
Companion to heal_experiment.py. The script that produced the Phase 1 finding
after the heal-revive lever returned a null result.

QUESTION: the full 17-card Special Tactics pool inflates length ~+31-36%. How
much is (a) half-team-speed, (b) stagger, or (c) irreducible combat friction?
METHOD: toggle each penalty OFF at the config level and measure the tax.

FINDING (2 seeds x 800, V6_CONFIG("standard9")):
    base (no pool)          33.15
    full pool               43.56   tax = +10.41
    full, half-speed OFF    41.31   -> half-speed  +2.26 (~22%)
    full, stagger OFF       44.03   -> stagger      ~0
    full, BOTH OFF          41.15   -> combat friction +8.00 (~77%)
=> the length tax is mostly irreducible combat friction; healing cannot
dissolve it. (Figures wobble with N/seed; the 77/22/~0 split is robust.)

NOTE: predates the V7 draft fix, so absolute lengths were on ~2.9-gladiator
teams. Re-run on V7 4-gladiator teams is item 6 of the test sequence.

Run:  python3 p1_decomp.py
"""
import random
import statistics

import cybershot_sim as C
import special_harness as H

C.PRUNED = {'RecoilHarness', 'StaticCloak', 'RedlineArray', 'Caltraps'}
SEEDS = [1, 2]
N = 800


def enable_pool():
    H.install(); H.reset()
    H.HS.pool_enabled = set(H.V6_SET); H.HS.pool_copies = 1; H.HS.max_specials = 2


def summ(cfg, seed):
    rng = random.Random(seed)
    return C.summarize([C.play_game(cfg, rng) for _ in range(N)], cfg)


def cell(pool, mod=None):
    if pool:
        enable_pool()
    cfg = C.V6_CONFIG("standard9")
    if mod:
        mod(cfg)
    S = [summ(cfg, s) for s in SEEDS]
    if pool:
        H.uninstall()
    return (statistics.mean(x['avg_rounds'] for x in S),
            statistics.mean(x['timeout_rate'] for x in S))


def main():
    b, _ = cell(False)
    f0, t0 = cell(True)
    fhs, ths = cell(True, lambda c: setattr(c, 'down_team_move_factor', 1.0))
    fst, tst = cell(True, lambda c: setattr(c, 'down_stagger', 0.0))

    def both(c):
        c.down_team_move_factor = 1.0
        c.down_stagger = 0.0

    fb, tb = cell(True, both)
    print(f"=== TAX DECOMPOSITION (full pool, V6 std9, {len(SEEDS)} seeds x {N}) ===")
    print(f"base (no pool)          : {b:6.2f}")
    print(f"full pool               : {f0:6.2f}  tax=+{f0-b:5.2f}  t/out={t0:.3f}")
    print(f"full, half-speed OFF    : {fhs:6.2f}  tax=+{fhs-b:5.2f}  t/out={ths:.3f}  (half-speed {f0-fhs:+.2f})")
    print(f"full, stagger OFF       : {fst:6.2f}  tax=+{fst-b:5.2f}  t/out={tst:.3f}  (stagger {f0-fst:+.2f})")
    print(f"full, BOTH OFF          : {fb:6.2f}  tax=+{fb-b:5.2f}  t/out={tb:.3f}  (residual friction +{fb-b:.2f})")


if __name__ == "__main__":
    main()
