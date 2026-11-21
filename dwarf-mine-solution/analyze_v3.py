"""Post-collection v3 diagnostics (run when gate_train/val.npz land).

Q1 v2 scores per split; Q2 TP capture vs labels; Q3 in-gate Z0 rate;
Q4 frame spreads TP-vs-FP; Q5 near-confirm kills; Q6 far-TP coords.
"""
import sys, os, glob
import numpy as np
sys.path.insert(0, '/home/user')
from offline_search import load
from v3_search import score_v3, rings_of
from offline_search import show


def labcount(split):
    """Per-(fi,k) label counts from raw."""
    out = {}
    for fi, f in enumerate(sorted(glob.glob(f'{split}/*.npz'))):
        d = np.load(f)
        lab = d['labels']
        off = d['frame_offsets']
        for k in range(len(off) - 1):
            out[(fi, k)] = int((lab[off[k]:off[k + 1]] == 1).sum())
    return out


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


def main():
    paths = {'train': ('train_units.npz', 'train_posframes.npz'),
             'val': ('units_val.npz', 'posframes_val.npz')}
    for split in ['train', 'val']:
        u, p = paths[split]
        D = load(f'gate_{split}.npz', u, p)
        r = D['recs']
        print(f'===== {split}: {len(r)} recs, {D["F"]} frames =====')
        d = score_v3(D)  # v2 point
        show('v2-point', d)
        sel = v2sel(r)
        gf = r['gf'].astype(int)
        isTP = r['obj'] >= 0
        # Q3: in-gate Z0 label rate
        z0 = r['Z'] == 0.0
        print(f'Q3: v2sel Z0: {(sel & z0).sum()}, TP frac='
              f'{(sel & z0 & isTP).sum() / max((sel & z0).sum(), 1):.3f}; '
              f'non-Z0 TP frac='
              f'{(sel & ~z0 & isTP).sum() / max((sel & ~z0).sum(), 1):.3f}')
        # Q6: far-TP coords
        ftp = sel & isTP & (r['X'] > 15.0)
        print(f'Q6: far(X>15) TP recs: {ftp.sum()}')
        if ftp.sum():
            print(f'   lat p50/p90={np.median(np.abs(r["lat"][ftp])):.3f}/'
                  f'{np.percentile(np.abs(r["lat"][ftp]), 90):.3f} zrel p10/'
                  f'p50={np.percentile(r["zrel"][ftp], 10):.3f}/'
                  f'{np.median(r["zrel"][ftp]):.3f} Z0frac='
                  f'{(r["Z"][ftp] == 0.0).mean():.3f}')
        # Q4: per-frame spreads, TP-frames vs FP-frames (v2sel, pre-confirm)
        idx = np.nonzero(sel)[0]
        gsel = gf[idx]
        order = np.argsort(gsel, kind='stable')
        gsel = gsel[order]
        Xs = r['X'][idx][order]
        Ys = r['Y'][idx][order]
        Zs = r['Z'][idx][order]
        Ts = isTP[idx][order]
        Rg = rings_of(Xs, Ys, Zs)
        bnd = np.flatnonzero(np.diff(gsel, prepend=gsel[0] - 1,
                                     append=gsel[-1] + 1))
        tpxr, fpxr, tpyr, fpyr, tpng, fpng, tpz0, fpz0 = \
            [], [], [], [], [], [], [], []
        for a, b in zip(bnd[:-1], bnd[1:]):
            has_tp = Ts[a:b].any()
            xr = float(Xs[a:b].max() - Xs[a:b].min())
            yr = float(Ys[a:b].max() - Ys[a:b].min())
            ng = len(np.unique(Rg[a:b]))
            zf = float((Zs[a:b] == 0.0).mean())
            npts = b - a
            xmin = float(Xs[a:b].min())
            (tpxr if has_tp else fpxr).append((xr, npts, xmin))
            (tpyr if has_tp else fpyr).append(yr)
            (tpng if has_tp else fpng).append(ng)
            (tpz0 if has_tp else fpz0).append(zf)
        tpxr = np.array(tpxr)
        fpxr = np.array(fpxr)
        print(f'Q4: TP-frames={len(tpxr)} FP-frames={len(fpxr)}')
        for nm, a in [('TP', tpxr[:, 0]), ('FP', fpxr[:, 0] if len(fpxr) else [0])]:
            a = np.asarray(a, float)
            print(f'   Xrange {nm}: p50={np.median(a):.2f} p90='
                  f'{np.percentile(a, 90):.2f} p99={np.percentile(a, 99):.2f} '
                  f'max={a.max():.2f}')
        for nm, a in [('TP', tpyr), ('FP', fpyr)]:
            a = np.asarray(a, float)
            print(f'   Yrange {nm}: p50={np.median(a):.2f} p90='
                  f'{np.percentile(a, 90):.2f} max={a.max():.2f}')
        for nm, a in [('TP', tpng), ('FP', fpng)]:
            a = np.asarray(a, int)
            print(f'   rings {nm}: 1-ring frac={(a == 1).mean():.3f}')
        for nm, a in [('TP', tpz0), ('FP', fpz0)]:
            a = np.asarray(a, float)
            print(f'   Z0frac {nm}: mean={a.mean():.3f} frac>0.5='
                  f'{(a > 0.5).mean():.3f}')
        # TP-frames that spread vetoes would kill
        for vx in (1.0, 1.5, 2.0, 3.0):
            kill = ((tpxr[:, 0] > vx) & (tpxr[:, 2] > 5.0)).mean()
            save = ((fpxr[:, 0] > vx) & (fpxr[:, 2] > 5.0)).mean() \
                if len(fpxr) else 0
            print(f'   VXRANGE={vx}: TP-frame kill={kill:.3f} '
                  f'FP-frame kill={save:.3f}')
        # Q5: near-confirm kills (positive clips failing tot_c<8)
        clip_of = D['clip_of']
        C = D['C']
        gsel2 = gf[sel]
        tot = np.bincount(clip_of[gsel2], minlength=C)
        near = np.bincount(clip_of[gsel2[r['X'][sel] <= 11.0 + 1e-9]],
                           minlength=C)
        # positive clips: any TP rec?
        tpclip = np.zeros(C, bool)
        tpclip[clip_of[gf[sel & isTP]]] = True
        dead_nc = tpclip & (tot >= 15) & (near < 8)
        dead_cm = tpclip & (tot < 15)
        print(f'Q5: TP clips={tpclip.sum()} killed-by-CN={dead_nc.sum()} '
              f'killed-by-CMIN={dead_cm.sum()}')
    print('TIME now:', __import__('datetime').datetime.utcnow()
          .strftime('%H:%M:%S'))


if __name__ == '__main__':
    main()
