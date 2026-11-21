"""Clip motion-coherence calibration: gap-normalized per-frame rates of
(Xmin, mean-lat) for TP-clips vs FP-clips. Mirrors vetolib.clip_motion_ok.
FP-clips = selected clips with no TP selection; TP-clips = with TP."""
import sys
import numpy as np
sys.path.insert(0, '/home/user')
from offline_search import load

PATHS = {'train': ('train_units.npz', 'train_posframes.npz'),
         'val': ('units_val.npz', 'posframes_val.npz')}


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


def main(split):
    u, p = PATHS[split]
    D = load(f'gate_{split}.npz', u, p)
    r = D['recs']
    sel = v2sel(r)
    gf = r['gf'].astype(int)
    isTP = r['obj'] >= 0
    clip_of = D['clip_of']
    C = D['C']
    F = D['F']
    k_of = D['k_of']
    fcnt = np.bincount(gf[sel], minlength=F)
    fxmin = np.full(F, np.inf)
    np.minimum.at(fxmin, gf[sel], r['X'][sel])
    flat = np.bincount(gf[sel], weights=r['lat'][sel], minlength=F) / \
        np.maximum(fcnt, 1)
    fhtp = np.bincount(gf[sel & isTP], minlength=F) > 0
    tp_jl, fp_jl, tp_jx, fp_jx, tp_nf, fp_nf = \
        [], [], [], [], [], []
    for c in range(C):
        gfs = np.nonzero(clip_of == c)[0]
        gfs = gfs[np.argsort(k_of[gfs])]
        gfs = gfs[fcnt[gfs] > 0]
        if len(gfs) < 2:
            continue
        ks = k_of[gfs].astype(float)
        dk = np.diff(ks)
        dk[dk < 1] = 1
        jl = float((np.abs(np.diff(flat[gfs])) / dk).max())
        jx = float((np.abs(np.diff(fxmin[gfs])) / dk).max())
        has_tp = fhtp[gfs].any()
        (tp_jl if has_tp else fp_jl).append(jl)
        (tp_jx if has_tp else fp_jx).append(jx)
        (tp_nf if has_tp else fp_nf).append(len(gfs))
    for nm, a in [('TP', tp_jl), ('FP', fp_jl)]:
        a = np.asarray(a, float)
        print(f'{split} latrate {nm}: n={len(a)} p50={np.median(a):.3f} '
              f'p90={np.percentile(a, 90):.3f} ' +
              ' '.join(f'frac>{t}={(a > t).mean():.3f}'
                       for t in (0.3, 0.4, 0.5, 0.7)))
    for nm, a in [('TP', tp_jx), ('FP', fp_jx)]:
        a = np.asarray(a, float)
        print(f'{split} xrange {nm}: n={len(a)} p50={np.median(a):.3f} '
              f'p90={np.percentile(a, 90):.3f} ' +
              ' '.join(f'frac>{t}={(a > t).mean():.3f}'
                       for t in (1.0, 1.2, 1.5, 2.0)))
    for nm, a in [('TP', tp_nf), ('FP', fp_nf)]:
        a = np.asarray(a, int)
        print(f'{split} nframes {nm}: mean={a.mean():.1f} '
              f'frac<2={(a < 2).mean():.3f} frac<3={(a < 3).mean():.3f} '
              f'frac<4={(a < 4).mean():.3f}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'val')
