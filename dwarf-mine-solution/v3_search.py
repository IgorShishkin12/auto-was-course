"""v3 offline search: v2 gate + per-frame shape vetoes + soft confirm.

Frame vetoes (before clip confirm; frames with Xmin<=VXMIN exempt from
spread vetoes to protect near/occlusion TP):
  VXRANGE: veto frames with selected-X-range > VXRANGE (0=off)
  VLRANGE: veto frames with selected-lat-range > VLRANGE (0=off)
  VYRANGE: veto frames with selected raw-Y-range > VYRANGE (0=off)
  VRING_N/VRING_X: veto single-ring frames with npts>=VRING_N and
      Xmin<=VRING_X (0/0=off)
  VETOZ0: drop Z==0 points from selection (bool)
  Z0FRAC: veto frames with Z==0 fraction > Z0FRAC (0=off)
  FMIN: veto frames with fewer than FMIN selected points (0=off)
Clip level:
  CFMIN: kill clips with fewer than CFMIN selected frames (0=off)
  VJLAT/VJX: kill clips whose consecutive-frame |dlat|/|dxmin| max
      exceeds threshold = teleport veto (0=off)
  VREC: kill clips with xmin_last-xmin_first > VREC (0=off)
  CN: near-confirm count (0=off)
"""
import sys
import numpy as np
sys.path.insert(0, '/home/user')
from offline_search import load, show
from vetolib import frame_veto, clip_motion_ok


def rings_of(X, Y, Z):
    return np.round(np.degrees(np.arctan2(Z, np.hypot(X, Y)))).astype(int)


def score_v3(D, LAT=0.55, ZBOT=0.36, ZTOP=1.15, XCAP=13.0,
             CMIN=15, CX=11.0, CN=8, XNEAR=7.0, ZLOW=0.18,
             XF1=15.0, LATF=0.35, ZBF=0.55,
             VXRANGE=0.0, VLRANGE=0.0, VYRANGE=0.0, VXMIN=5.0, VXNEAR=0.0,
             VRING_N=0, VRING_X=0.0, VETOZ0=False, Z0FRAC=0.0,
             FMIN=0, CFMIN=0, VJLAT=0.0, VJX=0.0, VREC=0.0,
             FMOTION=0, FARBIG=0, VJN=1, VJNF=0):
    from offline_search import WIDE
    assert LAT <= WIDE['lat'] + 1e-9 and ZBOT >= WIDE['zlo'] - 1e-9 \
        and ZTOP <= WIDE['zhi'] + 1e-9 and XCAP <= WIDE['xmax'] + 1e-9
    r = D['recs']
    lat = np.abs(r['lat'])
    latraw = r['lat']
    z = r['zrel']
    X = r['X']
    sel = (lat <= LAT + 1e-9) & (z >= ZBOT - 1e-9) & (z <= ZTOP + 1e-9) & \
        (X > -1.0) & (X <= XCAP + 1e-9)
    sel = sel | ((X <= XNEAR + 1e-9) & (lat <= LAT + 1e-9) &
                 (z >= ZLOW - 1e-9) & (z <= ZTOP + 1e-9) & (X > -1.0))
    if XF1 > 0:
        sel = sel | ((X > XCAP + 1e-9) & (X <= XF1 + 1e-9) &
                     (lat <= LATF + 1e-9) & (z >= ZBF - 1e-9) &
                     (z <= ZTOP + 1e-9))
    has_yz = ('Y' in r.dtype.names) and ('Z' in r.dtype.names)
    Y = r['Y'] if has_yz else np.zeros(len(r), np.float32)
    Z = r['Z'] if has_yz else np.zeros(len(r), np.float32)
    if VETOZ0 and has_yz:
        sel = sel & (Z != 0.0)
    F, C = D['F'], D['C']
    gf = r['gf'].astype(int)
    isTP = r['obj'] >= 0
    # ---- per-frame shape vetoes ----
    need_veto = (VXRANGE > 0 or VLRANGE > 0 or VYRANGE > 0 or VRING_N > 0 or VXNEAR > 0
                 or Z0FRAC > 0 or FMIN > 0) and has_yz
    if need_veto:
        idx = np.nonzero(sel)[0]
        if len(idx):
            gsel = gf[idx]
            Xs = X[idx]
            Ys = Y[idx]
            Zs = Z[idx]
            Ls = latraw[idx]
            order = np.argsort(gsel, kind='stable')
            gsel = gsel[order]
            Xs = Xs[order]
            Ys = Ys[order]
            Zs = Zs[order]
            Ls = Ls[order]
            bounds = np.flatnonzero(np.diff(gsel, prepend=gsel[0] - 1,
                                            append=gsel[-1] + 1))
            drop_gf = []
            for a, b in zip(bounds[:-1], bounds[1:]):
                if frame_veto(Xs[a:b], Ys[a:b], Zs[a:b], Ls[a:b],
                              VXRANGE=VXRANGE, VLRANGE=VLRANGE,
                              VYRANGE=VYRANGE, VXMIN=VXMIN, VXNEAR=VXNEAR,
                              VRING_N=VRING_N, VRING_X=VRING_X,
                              Z0FRAC=Z0FRAC, FMIN=FMIN):
                    drop_gf.append(gsel[a])
            if drop_gf:
                sel[idx[np.isin(gsel, np.array(drop_gf))]] = False
    # ---- clip confirmation ----
    clip_of = D['clip_of']
    gsel = gf[sel]
    tot = np.bincount(clip_of[gsel], minlength=C)
    if CN > 0:
        near = np.bincount(clip_of[gsel[X[sel] <= CX + 1e-9]], minlength=C)
        dead = (tot < CMIN) | (near < CN)
        if FARBIG > 0:
            dead = dead & ~(tot >= FARBIG)
    else:
        dead = tot < CMIN
    # ---- clip frame-count + motion vetoes ----
    if (CFMIN > 0 or VJLAT > 0 or VJX > 0 or VREC > 0) and has_yz:
        fsel = np.bincount(gsel, minlength=F)
        fxmin = np.full(F, np.inf)
        np.minimum.at(fxmin, gsel, X[sel])
        flat = np.bincount(gsel, weights=latraw[sel], minlength=F) / \
            np.maximum(fsel, 1)
        k_of = D['k_of']
        for c in range(C):
            if dead[c]:
                continue
            gfs = np.nonzero(clip_of == c)[0]
            gfs = gfs[np.argsort(k_of[gfs])]
            gfs = gfs[fsel[gfs] > 0]
            if CFMIN > 0 and len(gfs) < CFMIN:
                dead[c] = True
                continue
            if (VJLAT > 0 or VJX > 0 or VREC > 0) and \
                    not clip_motion_ok(k_of[gfs], fxmin[gfs], flat[gfs],
                                       fsel[gfs], FMOTION=FMOTION,
                                       VJLAT=VJLAT, VJX=VJX, VREC=VREC,
                                       VJN=VJN, VJNF=VJNF):
                dead[c] = True
    if dead.any():
        keep = sel.copy()
        idx = np.nonzero(sel)[0]
        keep[idx[dead[clip_of[gf[idx]]]]] = False
        sel = keep
    gsel = gf[sel]
    selcnt = np.bincount(gsel, minlength=F)
    tpsel = sel & isTP
    tpcnt = np.bincount(gf[tpsel], minlength=F)
    w = selcnt > 0
    P = float((tpcnt[w] / selcnt[w]).mean()) if w.any() else 0.0
    if tpsel.any():
        go = gf[tpsel]
        co = clip_of[go]
        oo = r['obj'][tpsel].astype(int)
        gr = r['grp'][tpsel].astype(int)
        key = (co.astype(np.int64) * 9000000 + oo.astype(np.int64)) * 4 + gr
        ukey = np.unique(np.stack([key, go], axis=1), axis=0)
        hits = np.zeros(len(D['un']), int)
        uidx = {}
        for (fi, c, o, gg), i in D['unit_lut'].items():
            uidx[(c, o, gg)] = i
        from collections import defaultdict
        per = defaultdict(set)
        for kk, gg in ukey:
            gg = int(gg)
            kk = int(kk)
            grr = kk % 4
            kk //= 4
            oo = kk % 9000000
            cc = kk // 9000000
            per[(cc, oo, grr)].add(gg)
        for k, s in per.items():
            i = uidx.get(k)
            if i is not None:
                hits[i] = len(s)
    else:
        hits = np.zeros(len(D['un']), int)
    R = []
    for gr in (0, 1, 2):
        m = D['ugrp'] == gr
        if m.any():
            R.append(float((hits[m] / D['un'][m]).mean()))
    Rmean = float(np.mean(R)) if R else 0.0
    egsel = gsel[~D['is_pos_frame'][gsel]]
    csel_e = np.bincount(clip_of[egsel], minlength=C) > 0 if len(egsel) \
        else np.zeros(C, bool)
    FA = np.nonzero(csel_e)[0]
    Ff = len(FA) / len(D['opp']) if len(D['opp']) else 0.0
    S = Rmean * P * (1 - Ff) ** 2
    return dict(R=Rmean, Rg=R, P=P, F=Ff, S=S, nFA=len(FA),
                nsel=int(sel.sum()), nselfr=int(w.sum()))


if __name__ == '__main__':
    print('v3_search module ready (needs gate_train/val.npz with Y,Z)')
