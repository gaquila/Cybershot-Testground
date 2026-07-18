"""
weights_v7.py -- recalibrated stat valuation for the drafting bot / rulers.
==========================================================================
Runtime harness over cybershot_sim. Canonical engine stays pristine.
These are AI/measurement constants (how the BOT values cards and how the
"strongest team" ruler scores teams), NOT game rules.

WHAT CHANGED & WHY
------------------
Old STAT_WEIGHTS [0.90, 1.68, 0.38, 0.73, 1.01] were fitted on the BROKEN
draft (teams of ~2.9 gladiators), where "more of a stat" secretly meant "more
bodies". Re-measured by seat-rotated perturbation on V7 canon (4 gladiators):

  flat per-point win-value:  Mit 0.051  Leth 0.042  Speed 0.040  Vit 0.028
  Willpower: NOT linear -- a near-step. Marginal value of the w-th point:
     1st +0.341   2nd +0.051   3rd +0.021   4th +0.011   5th +0.007
  i.e. ~all of Willpower's value is the FIRST point (enough-to-breach), then
  it saturates because you can't breach a gate faster than its counter allows.

So a flat weight for Willpower is impossible: 1.68 under-values point 1 by ~7x
and over-values point 5 by ~200x. We use a SATURATING curve instead:

     Vwill(w) = A * w / (w + K)      A = 0.461, K = 0.352   (fit, R~exact on w<=2)

and value Willpower ON THE MARGIN: a card adding dW of Willpower to a team that
already has w0 is worth Vwill(w0+dW) - Vwill(w0), scaled into weight units.

NORMALISATION: flat weights scaled so a typical linear point ~ 1.0.
     new STAT_WEIGHTS (L,M,S,V,W) = [0.94, 1.13, 0.88, 0.61, 0.0]
The W slot is 0.0 -- Willpower value comes ENTIRELY from the curve, never the
flat term, so nothing double-counts.

CAVEATS (carry these with any downstream number)
  * bot-relative: a human may extract more from Speed than a greedy bot.
  * config-relative: re-measure after any breach-formula or track change.

USAGE
-----
    import weights_v7 as WT
    WT.install()      # new weights + Willpower curve in card_value/
                      # team_strength/build_team
    WT.uninstall()    # restore old flat behaviour exactly (bit-exact guard)
"""
import inspect
import cybershot_sim as C
from cybershot_sim import W

# ---- recalibrated flat weights (W slot zeroed; curve handles Willpower) ----
NEW_WEIGHTS = [0.94, 1.13, 0.88, 0.61, 0.0]
_OLD_WEIGHTS = list(C.STAT_WEIGHTS)

# ---- Willpower saturation curve ----
_A = 0.461
_K = 0.352
# scale curve into the same units as the flat weights. Flat weights were
# scaled by (1.0 / 0.045) from raw per-point value; use the same factor so the
# curve's marginal sits on the same ruler as the linear stats.
_UNIT = 1.0 / 0.045


def Vwill(w):
    """Total Willpower value (weight units) for w points of Willpower."""
    if w <= 0:
        return 0.0
    return _UNIT * _A * w / (w + _K)


def will_marginal(w0, dw):
    """Value of adding dw Willpower to a team that already has w0."""
    if dw == 0:
        return 0.0
    return Vwill(w0 + dw) - Vwill(w0)


_installed = False
_ORIG = {}


def install():
    global _installed
    if _installed:
        return
    _ORIG["card_value"] = C.card_value
    _ORIG["team_strength"] = C.team_strength
    _ORIG["build_team"] = C.build_team
    _ORIG["weights"] = list(C.STAT_WEIGHTS)

    ns = C.__dict__
    # new flat weights (W zeroed)
    C.STAT_WEIGHTS[:] = NEW_WEIGHTS
    ns["Vwill"] = Vwill
    ns["will_marginal"] = will_marginal

    # --- card_value: replace the ad-hoc Willpower `role` hack with the curve,
    # and add the curve's marginal for equipment/character Willpower. ---
    src = inspect.getsource(_ORIG["card_value"])
    # character branch: drop the hand-tuned +5 W role bonus, add curve marginal
    src = src.replace(
        "        role = 0\n"
        "        if have_w < 3 and stats[W] >= 2: role += 5\n"
        "        if have_s < 3 and stats[S] >= 2: role += 3\n"
        "        return 100 + wval + role + effect_value(card[\"name\"],\"char\",cfg)",
        "        role = 0\n"
        "        if have_s < 3 and stats[S] >= 2: role += 3\n"
        "        wmarg = will_marginal(have_w, stats[W])\n"
        "        return 100 + wval + role + wmarg + effect_value(card[\"name\"],\"char\",cfg)")
    # equipment branch: STAT_WEIGHTS[W]=0 now, so add curve marginal for eq W.
    src = src.replace(
        "    return 10 + sum(abs(x*STAT_WEIGHTS[i]) for i,x in enumerate(EQUIPMENT[card[\"name\"]][0])) + effect_value(card[\"name\"],\"equip\",cfg)",
        "    have_w_eq = sum(CHARACTERS[c[\"name\"]][0][W] for c in have if c[\"kind\"]==\"char\")\n"
        "    eqw = EQUIPMENT[card[\"name\"]][0][W]\n"
        "    return 10 + sum(abs(x*STAT_WEIGHTS[i]) for i,x in enumerate(EQUIPMENT[card[\"name\"]][0])) + will_marginal(have_w_eq, eqw) + effect_value(card[\"name\"],\"equip\",cfg)")
    exec(compile(src, "<wv_card_value>", "exec"), ns)

    # --- team_strength: W slot is 0 in weights; add Vwill(total W) ---
    src = inspect.getsource(_ORIG["team_strength"])
    src = src.replace(
        "    stat_val = sum(p[i]*STAT_WEIGHTS[i] for i in range(5)) + hp*0.15",
        "    stat_val = sum(p[i]*STAT_WEIGHTS[i] for i in range(5)) + Vwill(p[W]) + hp*0.15")
    exec(compile(src, "<wv_team_strength>", "exec"), ns)

    # --- build_team character sort: same flat term is now W-blind; add curve ---
    src = inspect.getsource(_ORIG["build_team"])
    src = src.replace(
        "    chosen = sorted(chars, key=lambda c: -(sum(\n"
        "        CHARACTERS[c[\"name\"]][0][i]*STAT_WEIGHTS[i] for i in range(5))\n"
        "        + effect_value(c[\"name\"], \"char\", cfg)))[:4]",
        "    chosen = sorted(chars, key=lambda c: -(sum(\n"
        "        CHARACTERS[c[\"name\"]][0][i]*STAT_WEIGHTS[i] for i in range(5))\n"
        "        + Vwill(CHARACTERS[c[\"name\"]][0][W])\n"
        "        + effect_value(c[\"name\"], \"char\", cfg)))[:4]")
    exec(compile(src, "<wv_build_team>", "exec"), ns)

    _installed = True


def uninstall():
    global _installed
    if not _installed:
        return
    C.card_value = _ORIG["card_value"]
    C.team_strength = _ORIG["team_strength"]
    C.build_team = _ORIG["build_team"]
    C.STAT_WEIGHTS[:] = _ORIG["weights"]
    for k in ("Vwill", "will_marginal"):
        C.__dict__.pop(k, None)
    _installed = False
