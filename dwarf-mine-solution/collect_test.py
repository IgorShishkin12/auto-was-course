"""Wide-gate collector for UNLABELED test: per-point (lat,zrel,X) + frame info.

Saves test_wide.npz: recs (gf,lat,zrel,X float), frames (fi,k,n,err,grade0),
files (names). Geometry identical to predict_mask (incl. _default_fit).
"""
import sys, os, glob
import numpy as np
sys.path.insert(0, '/home/user')
from tracklib import track_slices, fit_models, ring_profile_detections, \
    ransac_inliers, build_polyline, _default_fit


def frame_geo(p):
    info = {}
    try:
        tracked, grade0 = track_slices(p)
        fit0 = fit_models(tracked, grade0, p)
    except Exception as e:
        info['err'] = f'track:{e}'
        tracked, grade0, fit0 = [], 0.0, {'ok': False}
    info['grade0'] = float(grade0)
    if not fit0.get('ok'):
        info['err'] = 'fit_fail_default'
        fit = _default_fit(p)
        allst = []
    else:
        z0, gg, pp = fit0['z0'], fit0['g'], fit0['p']
        Zb0 = lambda X: z0 + gg * np.asarray(X, float) + pp * np.asarray(X, float) ** 2
        try:
            prof = ring_profile_detections(p, Zb0)
        except Exception:
            prof = []
        allst = tracked + prof
        fit = fit_models(allst, grade0, p)
        if not fit.get('ok'):
            fit = fit0
            allst = tracked
    inl = ransac_inliers(allst)
    Xp, Yp, Zp, Tp = build_polyline(fit, inl)
    dx = p[:, 0:1] - Xp[None, :]
    dy = p[:, 1:2] - Yp[None, :]
    j = np.argmin(dx * dx + dy * dy, axis=1)
    j2 = np.minimum(j + 1, len(Xp) - 1)
    j1 = np.maximum(j - 1, 0)
    tx = Xp[j2] - Xp[j1]
    ty = Yp[j2] - Yp[j1]
    n = np.hypot(tx, ty) + 1e-12
    lat = (-(p[:, 0] - Xp[j]) * ty + (p[:, 1] - Yp[j]) * tx) / n
    zrel = p[:, 2] - (Zp[j] - 0.02)
    return lat, zrel, info


def main(dataroot, outpath, limit=None):
    files = sorted(glob.glob(os.path.join(dataroot, '*.npz')))
    if limit:
        files = files[:limit]
    recs = []
    frames = []
    gf = 0
    for fi, f in enumerate(files):
        d = np.load(f)
        pts = d['points']
        off = d['frame_offsets']
        T = len(off) - 1
        for k in range(T):
            p = pts[off[k]:off[k + 1]]
            try:
                lat, zrel, info = frame_geo(p)
            except Exception as e:
                frames.append((fi, k, len(p), 2, 0.0))
                gf += 1
                continue
            err = 0 if 'err' not in info else 1
            frames.append((fi, k, len(p), err, info.get('grade0', 0.0)))
            m = (np.abs(lat) <= 0.70 + 1e-9) & (zrel >= 0.10 - 1e-9) & \
                (zrel <= 1.50 + 1e-9) & (p[:, 0] > -1.0) & (p[:, 0] <= 25.0)
            idx = np.nonzero(m)[0]
            for i in idx:
                recs.append((gf, float(lat[i]), float(zrel[i]),
                             float(p[i, 0]), float(p[i, 1]),
                             float(p[i, 2])))
            gf += 1
        if (fi + 1) % 50 == 0:
            print(f'{fi+1}/{len(files)} recs={len(recs)}', flush=True)
    rdt = np.dtype([('gf', '<i4'), ('lat', '<f4'), ('zrel', '<f4'),
                    ('X', '<f4'), ('Y', '<f4'), ('Z', '<f4')])
    fdt = np.dtype([('fi', '<i4'), ('k', '<i4'), ('n', '<i4'),
                    ('err', '<i2'), ('g0', '<f4')])
    np.savez_compressed(outpath,
                        recs=np.array(recs, dtype=rdt),
                        frames=np.array(frames, dtype=fdt),
                        files=np.array([os.path.basename(f) for f in files]))
    print(f'saved {outpath}: {len(recs)} pts, {len(frames)} frames')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
