"""Collect per-point gate coords for in-gate points over a split.
Saves gate_data.npz: per in-gate point (frame_global, lat, zrel, X, obj, group),
plus frame table (file_id, frame_in_file, n_total) for metric recompute."""
import sys, os, glob
import numpy as np
sys.path.insert(0, '/home/user')
from tracklib import track_slices, fit_models, ring_profile_detections, \
    ransac_inliers, build_polyline, _default_fit

def frame_points(p):
    try:
        tracked, grade0 = track_slices(p)
        fit0 = fit_models(tracked, grade0, p)
    except Exception:
        tracked, grade0, fit0 = [], 0.0, {'ok': False}
    if not fit0.get('ok'):
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
    return lat, zrel

def main(dataroot, outpath):
    files = sorted(glob.glob(os.path.join(dataroot, '*.npz')))
    recs = []  # (gframe, lat, zrel, X, obj, group)
    frames = []  # (file_idx, frame_in_file, n_pts)
    gf = 0
    for fi, f in enumerate(files):
        d = np.load(f)
        pts = d['points']; off = d['frame_offsets']
        lab = d['labels']; ids = d['object_ids']
        T = len(off) - 1
        for k in range(T):
            s, e = off[k], off[k + 1]
            p = pts[s:e]
            frames.append((fi, k, e - s))
            r = frame_points(p)
            if r is None:
                gf += 1
                continue
            lat, zrel = r
            # WIDE collection for operating-point search (v2+): lat to
            # 0.70, zrel from 0.10 (low objects/rails), X to 25, top 1.50
            m = (np.abs(lat) <= 0.70 + 1e-9) & (zrel >= 0.10 - 1e-9) & \
                (zrel <= 1.50 + 1e-9) & (p[:, 0] > -1.0) & (p[:, 0] <= 25.0)
            idx = np.where(m)[0]
            if len(idx):
                l = lab[s:e]
                io = ids[s:e]
                dist = np.linalg.norm(p, axis=1)
                # group per object in this frame
                grp_of = {}
                for obj in np.unique(io[l == 1]):
                    elg = (l == 1) & (io == obj)
                    grp_of[int(obj)] = int(np.searchsorted(
                        [10., 25.], np.median(dist[elg]), side='right'))
                for i in idx:
                    o = int(io[i]) if l[i] == 1 else -1
                    g = grp_of[o] if o >= 0 else -1
                    recs.append((gf, float(lat[i]), float(zrel[i]),
                                float(p[i, 0]), o, g))
            gf += 1
        print(f'{fi+1}/{len(files)} recs={len(recs)}', flush=True)
    recs = np.array(recs, dtype=[('gf', 'i4'), ('lat', 'f4'), ('zrel', 'f4'),
                                 ('X', 'f4'), ('obj', 'i4'), ('grp', 'i2')])
    frames = np.array(frames, dtype=[('fi', 'i4'), ('k', 'i4'), ('n', 'i4')])
    np.savez_compressed(outpath, recs=recs, frames=frames,
                        files=np.array([os.path.basename(f) for f in files]))
    print(f'saved {outpath}: {len(recs)} in-gate pts, {len(frames)} frames')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
