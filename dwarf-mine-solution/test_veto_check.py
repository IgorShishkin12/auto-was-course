"""Test-side v3 trial (no labels): alive files under v2 gate + vetoes.

Mirrors v3_search.score_v3 clip logic (clip=file for test, T=10).
Usage: python3 test_veto_check.py [k=v ...]
Saves /tmp/test_alive.npy (file indices) and prints kill reasons.
"""
import sys
import numpy as np
sys.path.insert(0, '/home/user')
from vetolib import frame_veto, clip_motion_ok


def v2sel(r):
    lat = np.abs(r['lat'])
    z = r['zrel']
    X = r['X']
    return ((lat <= 0.55 + 1e-9) & (z >= 0.36 - 1e-9) & (z <= 1.15 + 1e-9) &
            (X > -1.0) & (X <= 13.0 + 1e-9)) | \
        ((X <= 7.0 + 1e-9) & (lat <= 0.55 + 1e-9) & (z >= 0.18 - 1e-9) &
         (z <= 1.15 + 1e-9) & (X > -1.0)) | \
        ((X > 13.0 + 1e-9) & (X <= 15.0 + 1e-9) & (lat <= 0.35 + 1e-9) &
         (z >= 0.55 - 1e-9) & (z <= 1.15 + 1e-9))


P = dict(CMIN=15, CX=11.0, CN=8, FMIN=0, CFMIN=0,
         VXRANGE=0.0, VLRANGE=0.0, VYRANGE=0.0, VXMIN=5.0, VXNEAR=0.0,
         VRING_N=0, VRING_X=0.0, VETOZ0=0, Z0FRAC=0.0,
         VJLAT=0.0, VJX=0.0, VREC=0.0, FMOTION=0, FARBIG=0, VJN=1,
         VJNF=0)


def main():
    d = np.load('/home/user/test_wide.npz')
    r = d['recs']
    fr = d['frames']
    files = list(d['files'])
    sel = v2sel(r)
    gf = r['gf'].astype(int)
    X = r['X']
    Y = r['Y']
    Z = r['Z']
    L = r['lat']
    if P['VETOZ0']:
        sel = sel & (Z != 0.0)
    # per-frame vetoes
    n_vetofr = 0
    idx = np.nonzero(sel)[0]
    if len(idx) and (P['VXRANGE'] > 0 or P['VLRANGE'] > 0 or P['VYRANGE'] > 0
                     or P['VRING_N'] > 0 or P['VXNEAR'] > 0 or
                     P['Z0FRAC'] > 0 or P['FMIN'] > 0):
        gsel = gf[idx]
        order = np.argsort(gsel, kind='stable')
        gsel = gsel[order]
        Xs = X[idx][order]
        Ys = Y[idx][order]
        Zs = Z[idx][order]
        Ls = L[idx][order]
        bnd = np.flatnonzero(np.diff(gsel, prepend=gsel[0] - 1,
                                     append=gsel[-1] + 1))
        drop = []
        for a, b in zip(bnd[:-1], bnd[1:]):
            if frame_veto(Xs[a:b], Ys[a:b], Zs[a:b], Ls[a:b],
                          VXRANGE=P['VXRANGE'], VLRANGE=P['VLRANGE'],
                          VYRANGE=P['VYRANGE'], VXMIN=P['VXMIN'], VXNEAR=P['VXNEAR'],
                          VRING_N=P['VRING_N'], VRING_X=P['VRING_X'],
                          Z0FRAC=P['Z0FRAC'], FMIN=P['FMIN']):
                drop.append(gsel[a])
        if drop:
            n_vetofr = len(drop)
            sel[idx[np.isin(gsel, np.array(drop))]] = False
    # per-file (clip) decisions
    F = len(fr)
    fi_of = fr['fi'].astype(int)
    k_of = fr['k'].astype(int)
    nfiles = len(files)
    fsel = np.bincount(gf[sel], minlength=F)
    fxmin = np.full(F, np.inf)
    flat = np.zeros(F)
    if sel.any():
        np.minimum.at(fxmin, gf[sel], X[sel])
        flat = np.bincount(gf[sel], weights=L[sel], minlength=F) / \
            np.maximum(fsel, 1)
    alive = []
    reasons = {}
    for fi in range(nfiles):
        gfs = np.nonzero(fi_of == fi)[0]
        tot = int(fsel[gfs].sum())
        if tot < P['CMIN']:
            reasons[fi] = f'tot{tot}'
            continue
        if P['CN'] > 0:
            m = sel & np.isin(gf, gfs) & (X <= P['CX'] + 1e-9)
            if int(m.sum()) < P['CN'] and \
                    not (P['FARBIG'] > 0 and tot >= P['FARBIG']):
                reasons[fi] = f'near{int(m.sum())}'
                continue
        selfr = gfs[fsel[gfs] > 0]
        selfr = selfr[np.argsort(k_of[selfr])]
        if P['CFMIN'] > 0 and len(selfr) < P['CFMIN']:
            reasons[fi] = f'nf{len(selfr)}'
            continue
        if (P['VJLAT'] > 0 or P['VJX'] > 0 or P['VREC'] > 0) and \
                not clip_motion_ok(k_of[selfr], fxmin[selfr], flat[selfr],
                                   fsel[selfr], FMOTION=P['FMOTION'],
                                   VJLAT=P['VJLAT'], VJX=P['VJX'],
                                   VREC=P['VREC'], VJN=P['VJN'],
                                   VJNF=P['VJNF']):
            reasons[fi] = 'motion'
            continue
        alive.append(fi)
    print('params:', P)
    print(f'vetoed frames: {n_vetofr}  alive files: {len(alive)}/'
          f'{len(files)}  v2pts: {int(sel.sum())}')
    np.save('/tmp/test_alive.npy', np.array(alive))
    # kill reason histogram (only among files with any v2 selection)
    return alive, reasons, files


if __name__ == '__main__':
    for a in sys.argv[1:]:
        k, v = a.split('=')
        P[k] = float(v) if '.' in v or 'e' in v.lower() else int(v)
    main()
