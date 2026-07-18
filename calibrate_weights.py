"""
calibrate_weights.py -- recompute STAT_WEIGHTS by controlled perturbation.
==========================================================================
Runs ON TOP of v7 (install v7 first). Engine stays pristine.

METHOD (the logic George approved)
----------------------------------
STAT_WEIGHTS[i] should answer: "how many extra wins does +1 point of stat i
buy?" We measure it directly rather than regressing over messy games:

  1. Build n IDENTICAL mirror teams (same 4 gladiators, same gear) so the
     fair win rate is exactly 1/n and nothing else differs.
  2. Add +N points of ONE stat to team 0's gladiators (spread evenly). If the
     stat is Vitality, bump HP too, since HP = Vitality.
  3. Run a large batch. Lift = team0_winrate - 1/n. Marginal value = lift / N.
  4. Repeat for each stat, at two N values, to check rough linearity.
  5. Normalise so the numbers sit on a convenient scale.

WHY MIRROR, NOT DRAFT: in a drafted game "more Speed" is entangled with
whatever else the bot drafted alongside it. Mirror teams change exactly one
variable, so the lift is attributable to that stat alone -- and you can sanity
-check each number by eye.

CAVEATS (state these with the numbers)
  * Weights are BOT-RELATIVE: a human may extract more from Speed than a
    greedy bot. These calibrate the sim's drafting brain, not table reality.
  * Weights are CONFIG-RELATIVE: re-check after any big rule change.
  * A stat with a strong nonlinearity (e.g. HP breakpoints) will show N-
    dependence; we print both N values so that is visible, not hidden.
"""
import random
import statistics

import cybershot_sim as C
from cybershot_sim import L, M, S, V, W

STAT_NAMES = ["Lethality", "Mitigate", "Speed", "Vitality", "Willpower"]


def _mirror_teams(cfg, rng, roster):
    """n identical teams from a fixed 4-gladiator roster (list of char names)."""
    teams = []
    for pid in range(cfg.n_players):
        glads = []
        for nm in roster:
            base = list(C.CHARACTERS[nm][0])
            hp = max(1, base[V])
            glads.append(C.Gladiator(name=nm, base=base, quirk=None,
                                     hp=hp, maxhp=hp))
        t = C.Team(pid=pid, glads=glads)
        # neutral 11-card personal deck, same for everyone
        deck = (["MA"] * cfg.deck_MA + ["MB"] * cfg.deck_MB + ["BA"] * cfg.deck_BA
                + ["H"] * cfg.deck_H + ["MD"] * cfg.deck_MD + ["BD"] * cfg.deck_BD
                + ["AD"] * cfg.deck_AD)
        rng.shuffle(deck)
        t.deck = deck
        teams.append(t)
    return teams


def _perturb(team, stat, amount):
    """Add `amount` points of `stat` spread across the team's 4 gladiators."""
    per = amount // len(team.glads)
    extra = amount - per * len(team.glads)
    for k, g in enumerate(team.glads):
        add = per + (1 if k < extra else 0)
        g.base[stat] += add
        if stat == V:                       # Vitality drives HP
            g.hp += add
            g.maxhp += add


def measure(cfg, stat, amount, n_games, roster, seed=0):
    """Perturb one team by +amount of `stat`, ROTATING which seat it occupies
    across games so the structural seat bias (seat 0 ~+3pp over seat n-1 on
    identical teams) cancels out. Return its win-rate lift over 1/n."""
    rng = random.Random(seed)
    wins = 0
    n = cfg.n_players
    games_per_seat = max(1, n_games // n)
    total = games_per_seat * n
    for seat in range(n):
        for _ in range(games_per_seat):
            track = C.build_track(cfg.vault_scale, cfg.gate_counter, gates=(3, 6),
                                  vault_breach=cfg.vault_breach, layout=cfg.track_layout)
            C.ABILITY_CAP_ON = cfg.ability_cap
            C.N_LOC = len(track)
            teams = _mirror_teams(cfg, rng, roster)
            if amount:
                _perturb(teams[seat], stat, amount)
            res = C.run_engine(cfg, rng, teams, track)
            if res["winner"] == seat:
                wins += 1
    wr = wins / total
    return wr, 1.0


def run(cfg, n_games=1500, amounts=(2, 4), rosters=None, seed0=100):
    """Full calibration sweep. Returns dict stat->marginal value (avg over N)."""
    if rosters is None:
        # a few neutral mid-strength rosters to avoid quirk/ability artifacts
        names = [n for n in C.CHARACTERS]
        rosters = [names[0:4], names[4:8], names[8:12]]

    # control: unperturbed mirror should sit at ~1/n (sanity)
    base_wr, _ = measure(cfg, L, 0, n_games, rosters[0], seed=seed0)
    print(f"control (no perturbation) team0 WR = {base_wr:.3f}  "
          f"(expect ~{1.0/cfg.n_players:.3f})\n")

    print(f"{'stat':<11}" + "".join(f"  +{a} lift  val/pt" for a in amounts)
          + "   mean val/pt")
    raw = {}
    for stat in (L, M, S, V, W):
        cells = []
        percell = []
        for a in amounts:
            lifts = []
            for ri, roster in enumerate(rosters):
                wr, _ = measure(cfg, stat, a, n_games, roster, seed=seed0 + 1 + ri)
                lifts.append(wr - 1.0 / cfg.n_players)
            lift = statistics.mean(lifts)
            cells.append((lift, lift / a))
            percell.append(lift / a)
        raw[stat] = statistics.mean(percell)
        cellstr = "".join(f"  {lf:+.3f}  {vp:+.3f}" for lf, vp in cells)
        print(f"{STAT_NAMES[stat]:<11}{cellstr}   {raw[stat]:+.3f}")

    # normalise: clamp tiny/negative to a small floor, scale so max ~ old max
    print("\n--- proposed STAT_WEIGHTS ---")
    floor = 0.05
    clamped = {i: max(floor, raw[i]) for i in raw}
    scale = 1.68 / max(clamped.values())      # anchor peak to the old Mitigate 1.68
    weights = [round(clamped[i] * scale, 2) for i in range(5)]
    print("current:", [0.90, 1.68, 0.38, 0.73, 1.01])
    print("proposed:", weights)
    for i in range(5):
        print(f"  {STAT_NAMES[i]:<11} {weights[i]:.2f}")
    return raw, weights
