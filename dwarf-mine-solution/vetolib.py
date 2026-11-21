"""Shared v3 veto primitives. Used by BOTH offline tuning (v3_search)
and production prediction (predict_v3) so tuned params transfer exactly.

Conventions mirror tracklib/offline_search: float compares use +1e-9 tol.
"""
import numpy as np

TOL = 1e-9


def rings_of(X, Y, Z):
    return np.round(np.degrees(np.arctan2(Z, np.hypot(X, Y)))).astype(int)


def frame_veto(Xs, Ys, Zs, Ls, VXRANGE=0.0, VLRANGE=0.0, VYRANGE=0.0,
               VXMIN=5.0, VXNEAR=0.0, VRING_N=0, VRING_X=0.0, Z0FRAC=0.0,
               FMIN=0):
    """Decide whether to drop a frame's selection. Xs/... are 1-D arrays
    of the SELECTED points in one frame. Returns True = veto frame."""
    n = len(Xs)
    if n == 0:
        return False
    if FMIN > 0 and n < FMIN:
        return True
    xmin = float(Xs.min())
    if xmin <= VXMIN + TOL and VXNEAR > 0 and \
            float(Xs.max() - xmin) > VXNEAR + TOL:
        return True
    if xmin > VXMIN + TOL:
        if VXRANGE > 0 and float(Xs.max() - xmin) > VXRANGE + TOL:
            return True
        if VLRANGE > 0 and float(Ls.max() - Ls.min()) > VLRANGE + TOL:
            return True
        if VYRANGE > 0 and float(Ys.max() - Ys.min()) > VYRANGE + TOL:
            return True
    if VRING_N > 0 and n >= VRING_N and xmin <= VRING_X + TOL:
        if len(np.unique(rings_of(Xs, Ys, Zs))) <= 1:
            return True
    if Z0FRAC > 0 and float((Zs == 0.0).mean()) > Z0FRAC + TOL:
        return True
    return False


def clip_motion_ok(ks, xmins, latmeans, ns=None, FMOTION=0, VJLAT=0.0,
                   VJX=0.0, VREC=0.0, VJN=1, VJNF=0):
    """Clip-level teleport/recede veto. ks/xmins/latmeans: per
    selected-frame (frame idx, Xmin, mean-lat) sorted by frame.
    Jumps are gap-normalized (per-frame rates) so frames dropped by
    frame-vetoes don't create artificial jumps. Frames with npts <
    FMOTION are excluded from the trajectory (but their points stay
    selected). Returns True = keep."""
    ks = np.asarray(ks, float)
    xmins = np.asarray(xmins, float)
    latmeans = np.asarray(latmeans, float)
    if FMOTION > 0 and ns is not None:
        keep = np.asarray(ns) >= FMOTION
        ks, xmins, latmeans = ks[keep], xmins[keep], latmeans[keep]
    m = len(ks)
    if m < 2:
        return True
    dk = np.diff(ks)
    dk[dk < 1] = 1
    nbad = 0
    if VJLAT > 0:
        nbad += int((((np.abs(np.diff(latmeans)) / dk) > VJLAT + TOL)).sum())
    if VJX > 0:
        nbad += int((((np.abs(np.diff(xmins)) / dk) > VJX + TOL)).sum())
    if VJNF > 0 and nbad == 1 and m > VJNF:
        pass  # single jitter jump in a long track: forgive
    elif nbad >= VJN:
        return False
    if VREC > 0 and float(xmins[-1] - xmins[0]) > VREC + TOL:
        return False
    return True
