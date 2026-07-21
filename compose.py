"""Compose special_harness on top of v7+weights_v7 without reverting them.
special_harness captures _orig_* at IMPORT (pristine). We re-point them to the
LIVE (v7/weights-patched) functions right before H.install() so its wrappers
chain on top instead of replacing v7/weights. Restores on teardown."""
import cybershot_sim as C
import special_harness as H

# which harness _orig_* mirrors which engine name
_MAP = {
    "_orig_take_card":"take_card","_orig_build_team":"build_team","_orig_draw_hand":"draw_hand",
    "_orig_add_temp":"add_temp","_orig_apply_hack":"apply_hack","_orig_commit":"_commit_v2",
    "_orig_alloc":"allocate_damage","_orig_resolve_attack":"resolve_attack",
    "_orig_resolve_move":"resolve_move","_orig_make_pool":"make_pool",
    "_orig_build_track":"build_track","_orig_card_value":"card_value",
}
_saved={}

def install_harness_over_live():
    for oname,cname in _MAP.items():
        if hasattr(H,oname):
            _saved[oname]=getattr(H,oname)
            setattr(H,oname, getattr(C,cname))   # point at LIVE function
    H.install(); H.reset()

def uninstall_harness():
    H.uninstall()
    for oname,val in _saved.items():
        setattr(H,oname,val)                     # restore import-time refs
    _saved.clear()


# --- also thread enabled specials into the v7 gear pool ---
# v7_draft calls the module-global _gear_pool; wrap it so that when the harness
# pool is enabled, the enabled special codes are mixed into the gear winchester.
import v7 as _V7
_orig_gear_pool = _V7._gear_pool

def _gear_pool_with_specials(rng, n, hand_size, include_specials=False, special_names=None):
    try:
        enabled = list(_H_pool_enabled())
    except Exception:
        enabled = []
    return _orig_gear_pool(rng, n, hand_size,
                           include_specials=bool(enabled), special_names=enabled)

def _H_pool_enabled():
    return getattr(H.HS, "pool_enabled", set()) or set()

def enable_specials_in_v7_draft():
    _V7._gear_pool = _gear_pool_with_specials

def disable_specials_in_v7_draft():
    _V7._gear_pool = _orig_gear_pool
