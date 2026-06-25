"""
ARCHETYPE EDGE-CASE TEST
========================
Build hyper-specialized teams DIRECTLY (bypass draft) and pit them against balanced
teams and each other. FAIRNESS CONTROL: every gladiator gets the SAME stat budget
(15 points across [L,M,S,V,W]); archetypes differ only in DISTRIBUTION.

IMPORTANT CAVEAT: Uses fixed stat-lines, no drafting. Cannot see gear/char effects.
Archetype matchups only test structural balance of core stats. For effects, use
run_config() with enable_char_abilities/enable_loadout_abilities/enable_equip_abilities.

Config: locked V4 core (9-loc, 2 light gates gc=5, graduated slipstream slip3,
freeze, gate_attack 0.5, uncapped, new_combat, draw-1/play-2 scarcity economy).
"""
import random, statistics
import cybershot_sim as cs
from cybershot_sim import Config, Gladiator, Team, run_engine, build_track, team_strength, L,M,S,V,W

ARCH = {
    "Balanced":      [3,3,2,4,3],
    "Hacker-mild":   [3,2,2,4,4],   "Hacker-mod":   [2,2,2,3,6],   "Hacker-ext":   [1,1,2,2,9],
    "Cannon-mild":   [4,3,2,3,3],   "Cannon-mod":   [6,2,2,2,3],   "Cannon-ext":   [9,1,2,2,1],
    "Speed-mild":    [2,3,4,3,3],   "Speed-mod":    [2,2,6,3,2],   "Speed-ext":    [1,1,9,2,2],
    "Fortress-mild": [2,4,2,5,2],   "Fortress-mod": [2,5,1,5,2],   "Fortress-ext": [1,7,1,5,1],
}
for k,v in ARCH.items():
    assert sum(v)==15, (k, sum(v))

def V4():
    return Config(n_players=4, draft_type="winchester", new_combat=True, uncapped=True,
                  slipstream_bonus=3, slipstream_graduated=True, hack_disrupt="freeze",
                  gate_counter=5, gate_attack_prob=0.5, draw_per_turn=1, hand_size=4,
                  regroup=True, start_hand=4, first_entry_penalty=3)

def make_team(pid, line, cfg, rng):
    glads=[]
    for k in range(4):
        st=list(line); hp=max(2, st[V])
        glads.append(Gladiator(name=f"g{k}", base=st, quirk=None, tags=set(),
                               range_bonus=0, hp=hp, maxhp=hp, downed=False,
                               ability=None, endured=False))
    t=Team(pid, glads); t.quirks=set()
    t.deck=(["MA"]*cfg.deck_MA+["MB"]*cfg.deck_MB+["BA"]*cfg.deck_BA+["H"]*cfg.deck_H)
    if cfg.new_combat:
        t.deck += ["MD"]*cfg.deck_MD + ["BD"]*cfg.deck_BD + ["AD"]*cfg.deck_AD
    rng.shuffle(t.deck); t.draft_score=team_strength(t,cfg)
    return t

def run_matchup(cfg, names, n_games, seed=1234):
    rng=random.Random(seed)
    wins=[0]*len(names); to=0; ranks=[[] for _ in names]
    gates=() if cfg.gate_counter<=0 else (3,6)
    for _ in range(n_games):
        track=build_track(cfg.vault_scale, cfg.gate_counter, gates=gates)
        teams=[make_team(i, ARCH[names[i]], cfg, rng) for i in range(len(names))]
        res=run_engine(cfg, rng, teams, track)
        if res["winner"] is not None: wins[res["winner"]]+=1
        if res["timeout"]: to+=1
        order=sorted(range(len(teams)),
                     key=lambda p:(res["winner"]==p, res["progress"][p]), reverse=True)
        for rank,p in enumerate(order): ranks[p].append(rank+1)
    n=n_games
    return [w/n for w in wins], to/n, [statistics.mean(r) for r in ranks]

if __name__ == "__main__":
    print("="*72)
    print("TEST 1 — ONE specialist (moderate) vs THREE balanced.")
    print("healthy: 25-60%. >60% = dominates. <15% = specialization punished.")
    print("="*72)
    for spec in ["Balanced","Hacker-mod","Cannon-mod","Speed-mod","Fortress-mod"]:
        wr,to,rk=run_matchup(V4(), [spec,"Balanced","Balanced","Balanced"], 2000)
        bal=statistics.mean(wr[1:])
        print(f"{spec:<18} {wr[0]:>7.1%}  (balanced avg {bal:.1%}, timeout {to:.1%})")
