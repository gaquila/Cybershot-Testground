"""
Phase-1 experiment: bot heal-to-revive lever.
---------------------------------------------
Runtime monkeypatch over cybershot_sim. Engine stays PRISTINE.

The only bot heal-revive trigger lives in choose_actions_v2 (line ~684):

    if any_downed(team) and any("heal" in CARD_TYPES[c] for c in team.hand) and rng.random()<0.6:
        combat, ctgt = "heal", None

heal_team() already revives downed-first at 1 HP, which cancels the
half-team-speed penalty. So the ONLY blindness is that 0.6: 40% of the time
the bot holds a downed gladiator AND a heal card and declines to revive.

This module rewrites JUST that one literal to read a live global
`_HEAL_REVIVE_PROB` (default 0.6 => bit-exact inert). Setting it to 1.0 =
"never waste an available revive" (the cheap-revive upper-ish bound).

The rng.random() draw is PRESERVED at prob=1.0 (random() in [0,1) is always
< 1.0), so a given seed drafts identically and only the heal branch flips --
keeping baseline and treatment as comparable as possible.
"""
import inspect
import cybershot_sim as C

_TARGET = "rng.random()<0.6"
_REPLACE = "rng.random()<_HEAL_REVIVE_PROB"
_ORIG_FUNC = C.choose_actions_v2
_installed = False

def install(prob=0.6):
    """Patch choose_actions_v2 so the revive trigger fires at `prob`."""
    global _installed
    src = inspect.getsource(_ORIG_FUNC)
    assert src.count(_TARGET) == 1, f"expected 1 target literal, found {src.count(_TARGET)}"
    src = src.replace(_TARGET, _REPLACE)
    ns = C.__dict__                       # share the engine's real module globals
    ns["_HEAL_REVIVE_PROB"] = float(prob)
    exec(compile(src, "<heal_experiment>", "exec"), ns)   # rebinds ns['choose_actions_v2']
    _installed = True

def set_prob(prob):
    C.__dict__["_HEAL_REVIVE_PROB"] = float(prob)

def uninstall():
    global _installed
    C.choose_actions_v2 = _ORIG_FUNC
    C.__dict__.pop("_HEAL_REVIVE_PROB", None)
    _installed = False
