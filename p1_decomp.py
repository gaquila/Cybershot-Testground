import random, statistics
import cybershot_sim as C
import special_harness as H
C.PRUNED = {'RecoilHarness','StaticCloak','RedlineArray','Caltraps'}
SEEDS=[1,2]; N=800

def enable_pool():
    H.install(); H.reset()
    H.HS.pool_enabled=set(H.V6_SET); H.HS.pool_copies=1; H.HS.max_specials=2

def summ(cfg,seed):
    rng=random.Random(seed)
    return C.summarize([C.play_game(cfg,rng) for _ in range(N)],cfg)

def cell(pool, mod=None):
    if pool: enable_pool()
    cfg=C.V6_CONFIG("standard9")
    if mod: mod(cfg)
    S=[summ(cfg,s) for s in SEEDS]
    if pool: H.uninstall()
    return statistics.mean(x['avg_rounds'] for x in S), statistics.mean(x['timeout_rate'] for x in S)

b,_   = cell(False)
f0,t0 = cell(True)
fhs,ths=cell(True, lambda c: setattr(c,'down_team_move_factor',1.0))
fst,tst=cell(True, lambda c: setattr(c,'down_stagger',0.0))
def both(c): c.down_team_move_factor=1.0; c.down_stagger=0.0
fb,tb = cell(True, both)
print("=== TAX DECOMPOSITION (full pool, V6 std9, 2 seeds x 800) ===")
print(f"base (no pool)          : {b:6.2f}")
print(f"full pool               : {f0:6.2f}  tax=+{f0-b:5.2f}  t/out={t0:.3f}")
print(f"full, half-speed OFF    : {fhs:6.2f}  tax=+{fhs-b:5.2f}  t/out={ths:.3f}  (half-speed contributes {f0-fhs:+.2f} to length)")
print(f"full, stagger OFF       : {fst:6.2f}  tax=+{fst-b:5.2f}  t/out={tst:.3f}  (stagger contributes {f0-fst:+.2f} to length)")
print(f"full, BOTH OFF          : {fb:6.2f}  tax=+{fb-b:5.2f}  t/out={tb:.3f}  (residual pure-combat tax +{fb-b:.2f})")
