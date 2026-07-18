"""
build_bias.py -- Phase-2 experiment: is the specialization tax a BOT ARTIFACT?
=============================================================================
Additive runtime monkeypatch over cybershot_sim. Engine stays PRISTINE.
Design invariant: gain=0.0 is bit-exact inert vs the unpatched engine.

THE QUESTION
------------
archetype_v6.py shows every stat-specialist underperforming the balanced
control (V6 mild: Fortress 22.6%, Cannon 19.2%, Speed 16.4%, Hacker 15.6%
vs control 27.6%). But the bot allocates actions by GENERIC heuristics -- it
attacks at a fixed `aggro` (0.45, or catchup_aggro when trailing) regardless
of what it drafted. A human Speed player would race relentlessly; the bot
never plays to its build.

So: are specialists punished because the build is weak, or because the bot
cannot PLAY it? This is the same trap as Phase 1, where the length tax turned
out to be 77% mechanism and ~0% healing. Establish the number is real before
designing a card to fix it.

THE LEVER
---------
The only build-blind knob in the live decision path (choose_actions_v2) is:

    aggro = cfg.catchup_aggro if (cfg.focus_leader and trailing) else 0.45

This module source-transforms that ONE line to call `_build_aggro(team, cfg,
trailing)`, which tilts attack-propensity by the team's own stat profile:

    aggro = base + gain * (L_share - S_share)

A Lethality-heavy team attacks MORE; a Speed-heavy team attacks LESS and
therefore races more (with aggro low, the decision falls through to the
sprint / move branches). Clamped to [0, 1].

At gain=0.0 the expression returns `base` exactly -> bit-exact inert.

WHY THIS LEVER: it is stat-derived, not pid-derived, so it generalises to the
main sim and does not require the harness to whisper which team is the
specialist. It is deliberately minimal -- one knob, one hypothesis.

USAGE
-----
    import build_bias as BB
    BB.install(gain=0.0)    # inert (regression guard)
    BB.set_gain(1.5)        # build-aware
    BB.uninstall()

INTERPRETATION
--------------
If Speed/Hacker recover toward the control when the bot plays to build, the
specialization tax is substantially a MEASUREMENT ARTIFACT and those builds
need a human, not a new card. If they do not recover, the weakness is real
and card design proceeds with a known target.
"""
import inspect
import cybershot_sim as C

_TARGET = "aggro = cfg.catchup_aggro if (cfg.focus_leader and trailing) else 0.45"
_REPLACE = "aggro = _build_aggro(team, cfg, trailing)"
_ORIG_FUNC = C.choose_actions_v2
_installed = False

_BUILD_AGGRO_GAIN = 0.0


def _build_aggro(team, cfg, trailing):
    """Attack-propensity tilted by the team's own stat profile.

    gain=0.0 returns the engine's exact default -> bit-exact inert.
    """
    base = cfg.catchup_aggro if (cfg.focus_leader and trailing) else 0.45
    g = C.__dict__.get("_BUILD_AGGRO_GAIN", 0.0)
    if g == 0.0:
        return base
    p = C.pooled(team, cfg, C.halfway(team))
    tot = sum(p)
    if tot <= 0:
        return base
    tilt = (p[C.L] - p[C.S]) / tot      # >0 = kill-leaning, <0 = race-leaning
    a = base + g * tilt
    return 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)


def install(gain=0.0):
    global _installed
    src = inspect.getsource(_ORIG_FUNC)
    assert src.count(_TARGET) == 1, (
        f"expected exactly 1 aggro line in choose_actions_v2, found "
        f"{src.count(_TARGET)} -- engine changed, re-check this patch"
    )
    src = src.replace(_TARGET, _REPLACE)
    ns = C.__dict__
    ns["_build_aggro"] = _build_aggro
    ns["_BUILD_AGGRO_GAIN"] = float(gain)
    exec(compile(src, "<build_bias>", "exec"), ns)
    _installed = True


def set_gain(gain):
    C.__dict__["_BUILD_AGGRO_GAIN"] = float(gain)


def uninstall():
    global _installed
    C.choose_actions_v2 = _ORIG_FUNC
    C.__dict__.pop("_BUILD_AGGRO_GAIN", None)
    C.__dict__.pop("_build_aggro", None)
    _installed = False
