"""Track centerline estimation + gauge prediction, v1.

Per frame:
  1. Track the raised trackbed (strip + rails) forward from X=2.5m using
     local contrast (detrended: center vs average of both flanks).
  2. Fit smooth parametric models: Yc(X) = aX^2 + bX^3, Zb(X) = z0 + pX^2 + qX^3.
  3. Extend beyond last tracked station (circular Y, linear-grade Z).
  4. Gauge test with heading (cos-theta) correction.
"""
import numpy as np

# ---------------- tracking ----------------

def _ring_groups(rr, gap):
    """Split sorted ranges into groups at gaps > gap. Returns list of index arrays."""
    idx = np.argsort(rr)
    s = rr[idx]
    splits = np.where(np.diff(s) > gap)[0]
    groups = []
    start = 0
    for sp in splits:
        groups.append(idx[start:sp + 1])
        start = sp + 1
    groups.append(idx[start:])
    return groups


def _estimate_grade0(p, zb_ref=-0.87):
    """Secant ground grade from origin via ring ground ranges (independent
    of tracking). Per ring: beam z=-tan|e|*x meets ground z=zb_ref+gr*x at
    x_med -> gr = -zb_ref/x_med - tan|e|. Median over near rings."""
    hxy = np.hypot(p[:, 0], p[:, 1])
    el = np.degrees(np.arctan2(p[:, 2], hxy))
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    rr = np.linalg.norm(p, axis=1)
    er = np.round(el).astype(int)
    grs = []
    for e in range(-15, -5):
        m = (er == e) & (np.abs(az) < 4.0) & (p[:, 2] > -1.6) & (p[:, 2] < 0.3)
        if m.sum() < 5:
            continue
        x_med = float(np.median(rr[m] * np.cos(np.radians(abs(e)))))
        if x_med < 1.5:
            continue
        grs.append(-zb_ref / x_med - np.tan(np.radians(abs(e))))
    if len(grs) < 3:
        return 0.0
    return float(np.clip(np.median(grs), -0.12, 0.12))


def track_slices(p):
    """Ring-based trackbed tracking (near->far rings). Within each ring,
    local contrast (center vs symmetric flanks on the same ring arc) finds
    the raised strip; rail pairs refine. Returns (list of dicts:
    x, yc, zb_strip, zb_rail, contrast, n_cen, coast, el; grade0 secant)."""
    hxy = np.hypot(p[:, 0], p[:, 1])
    el = np.degrees(np.arctan2(p[:, 2], hxy))
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    rr = np.linalg.norm(p, axis=1)
    er = np.round(el).astype(int)
    out = []
    yc_pred = 0.0
    head = 0.0
    zb_pred = -0.85
    # bootstrap: strip level under cart + secant grade from ring ranges
    _m0 = (p[:, 0] > 2.2) & (p[:, 0] < 3.8) & (np.abs(p[:, 1]) < 0.28) & \
        (p[:, 2] > -1.2) & (p[:, 2] < -0.5)
    zb_ref = float(np.median(p[_m0, 2])) if _m0.sum() >= 8 else -0.87
    grade0 = _estimate_grade0(p, zb_ref)
    grade = grade0
    x_prev = 3.0
    coast_run = 0
    zb_hist = []
    els = list(range(-15, 0))
    far_cands = []  # independent far detections (validated later)
    for e in els + [0, 1]:
        if e == 0 and grade < 0.012:
            continue
        if e == 1 and grade < 0.030:
            continue
        far_mode = e in (-3, -2, -1, 0, 1)
        m = er == e
        if m.sum() < 4:
            if not far_mode:
                coast_run += 1
            continue
        geff = float(np.clip(grade, -0.12, 0.12))
        if e < 0:
            # grade-aware: beam meets sloped ground closer (uphill)
            denom = np.tan(np.radians(abs(e))) + geff
            denom = max(denom, 0.25 * np.tan(np.radians(abs(e))))
            x_flat = -zb_pred / denom
            r_exp = -zb_pred / max(np.sin(np.radians(abs(e))) +
                                   geff * np.cos(np.radians(abs(e))), 1e-6)
        elif e == 0:
            x_flat = (0.0 - zb_pred) / max(geff, 0.012)
            r_exp = x_flat
        else:
            x_flat = (geff * x_prev - zb_pred) / max(geff - 0.0175, 0.005)
            r_exp = x_flat
        if not (2.0 < x_flat < 62):
            if not far_mode:
                coast_run += 1
            continue
        x_flat = float(x_flat)
        w = max(float(np.degrees(np.arctan2(0.9, x_flat))) + 2.0,
                3.5 + 1.5 * coast_run)
        w = min(w, 14.0)
        if far_mode:
            w = max(w, 9.0)
        az_pred = float(np.degrees(np.arctan2(yc_pred + head * max(x_flat - x_prev, 0),
                                              x_flat)))
        sel = np.abs(az[m] - az_pred) < w
        if sel.sum() < 8:
            if not far_mode:
                coast_run += 1
            continue
        idx = np.where(m)[0][sel]
        zbp = zb_pred + float(np.clip(grade, -0.15, 0.15)) * max(x_flat - x_prev, 0)
        hw = min(0.35 + 0.05 * coast_run, 0.65)
        if far_mode:
            hw = 0.70
        gmask = (p[idx, 2] > zbp - hw) & (p[idx, 2] < zbp + hw)
        if gmask.sum() < 6:
            coast_run += 1
            continue
        g = p[idx[gmask]]
        gr = rr[idx[gmask]]
        dx_pred = max(x_flat - x_prev, 0)
        sw = min(0.55 + 0.08 * coast_run, 1.10)
        yc0 = yc_pred + head * dx_pred
        # far rings: prediction uncertain (heading error x distance) -> widen
        # search and validation tolerances with distance
        tol_far = min(0.30 + 0.035 * dx_pred + 0.10 * coast_run, 1.30)
        if far_mode:
            sw = 3.0
            tol_far = 2.5
        # ---- primary: level rail pairs (spacing ~0.6, |dZ|<0.03) ----
        # local-peak test: rails stand above strip neighbors 6-18cm away
        # (same-rail points within 5cm are excluded from neighbors)
        def _is_peak(k):
            ady = np.abs(g[:, 1] - g[k, 1])
            nb = g[(ady > 0.06) & (ady < 0.18), 2]
            if len(nb) < 1:
                return x_flat > 12.0  # sparse far: skip peak test
            return g[k, 2] > np.median(nb) + 0.030
        zsorted = np.argsort(-g[:, 2])
        used = np.zeros(len(g), bool)
        pairs = []
        for ii in zsorted[:28]:
            if used[ii]:
                continue
            if not _is_peak(ii):
                continue
            dy = np.abs(g[:, 1] - g[ii, 1])
            dz = np.abs(g[:, 2] - g[ii, 2])
            dx = np.abs(g[:, 0] - g[ii, 0])
            pm = (~used) & (dy > 0.52) & (dy < 0.68) & (dz < 0.030) & (dx < 0.6)
            pm[ii] = False
            if not pm.any():
                continue
            # best partner: smallest dz (level!), must also be a peak
            cands = np.where(pm)[0]
            cands = cands[np.argsort(dz[cands])]
            for jj in cands[:3]:
                if not _is_peak(jj):
                    continue
                yl, yh = min(g[ii, 1], g[jj, 1]), max(g[ii, 1], g[jj, 1])
                between = g[(g[:, 1] > yl + 0.08) & (g[:, 1] < yh - 0.08), 2]
                zlvl = 0.5 * (g[ii, 2] + g[jj, 2])
                if len(between) >= 1 and zlvl > np.median(between) + 0.04:
                    pairs.append((0.5 * (g[ii, 1] + g[jj, 1]), zlvl,
                                  0.5 * (g[ii, 0] + g[jj, 0])))
                    used[ii] = True
                    used[jj] = True
                    break
        rail_hit = None
        if pairs:
            # pick pair nearest prediction (continuity)
            pairs.sort(key=lambda t: abs(t[0] - yc0))
            tol = tol_far + (0.15 if e == -15 else 0.0)
            if abs(pairs[0][0] - yc0) <= tol:
                rail_hit = pairs[0]
        yc_new, zc, c, ncen = None, None, 0.0, 0
        xmed = x_flat
        if rail_hit is not None:
            yc_new, zlvl, xmed = (float(rail_hit[0]), float(rail_hit[1]),
                                  float(rail_hit[2]))
            c, ncen = 0.10, 6
            # strip level between rails
            btw = g[(np.abs(g[:, 1] - yc_new) < 0.22), 2]
            btw = btw[btw < zlvl - 0.035]
            zc = float(np.median(btw)) if len(btw) >= 2 else zlvl - 0.09
        else:
            # ---- fallback: strip contrast (widen search far) ----
            sw_fb = min(sw + 0.03 * dx_pred, 1.30)
            if far_mode:
                sw_fb = sw
            best = None
            yc_cand = yc0 - sw_fb
            while yc_cand <= yc0 + sw_fb + 1e-9:
                d = g[:, 1] - yc_cand
                cen = g[np.abs(d) < 0.28, 2]
                lf = g[(d > 0.75) & (d < 1.40), 2]
                rf = g[(d < -0.75) & (d > -1.40), 2]
                if len(cen) >= 3 and len(lf) >= 2 and len(rf) >= 2:
                    cc = np.median(cen) - 0.5 * (np.median(lf) + np.median(rf))
                    if best is None or cc > best[0]:
                        best = (cc, yc_cand, np.median(cen), len(cen))
                yc_cand += 0.05
            if best is None or best[0] < 0.018 or best[0] > 0.11:
                if not far_mode:
                    coast_run += 1
                continue
            c, yc_new, zc, ncen = (float(best[0]), float(best[1]),
                                   float(best[2]), int(best[3]))
            # fallback continuity: reject jumps (would corrupt prediction);
            # tolerance scales with prediction distance (heading error)
            c_tol = min(0.18 + 0.04 * dx_pred + 0.05 * coast_run, 0.80)
            if abs(yc_new - yc0) > c_tol and not far_mode:
                coast_run += 1
                continue
            dc = np.abs(g[:, 1] - yc_new) < 0.28
            if dc.sum() >= 2:
                xmed = float(np.median(g[dc, 0]))
        # range sanity: strip range vs expected (looser in far mode)
        dc = np.abs(g[:, 1] - yc_new) < 0.30
        rmed = float(np.median(gr[dc])) if dc.sum() >= 2 else r_exp
        if far_mode:
            rng_ok = (0.40 * r_exp <= rmed <= 2.20 * r_exp)
        else:
            rng_ok = (0.55 * r_exp <= rmed <= 1.60 * r_exp)
        if not rng_ok:
            if not far_mode:
                coast_run += 1
            continue
        rec = {'x': xmed, 'yc': yc_new, 'zb_strip': zc, 'zb_rail': np.nan,
               'contrast': c, 'n_cen': ncen, 'coast': False, 'el': e}
        if rail_hit is not None:
            rec['zb_rail'] = zlvl - 0.07
        else:
            # rail check for zb (single ok): peaks near yc_new +- 0.3
            d = g[:, 1] - yc_new
            zb_r = []
            for sgn in (1.0, -1.0):
                wm = (d * sgn > 0.16) & (d * sgn < 0.46)
                if wm.sum() >= 1:
                    wv = g[wm, 2]
                    zmax = wv.max()
                    if zmax > zc + 0.045:
                        zb_r.append(zmax - 0.07)
            if len(zb_r) == 2 and abs(zb_r[0] - zb_r[1]) < 0.05:
                rec['zb_rail'] = float(np.mean(zb_r))
            elif len(zb_r) == 1:
                rec['zb_rail'] = float(zb_r[0])
        # zb jump sanity (object covering?): don't trust zb if jump > 6cm
        zb_best = rec['zb_rail'] if not np.isnan(rec['zb_rail']) else zc + 0.02
        if abs(zb_best - zbp) > 0.09 and np.isnan(rec['zb_rail']):
            rec['zb_strip'] = np.nan
            zb_best = zbp  # coast zb
            use_zb = False
        else:
            use_zb = True
        if far_mode:
            # independent detection: do not touch chain state; store for
            # post-validation against the near fit
            rec['zb_strip'] = zb_best
            far_cands.append(rec)
            continue
        dx = xmed - x_prev
        if dx > 0.2:
            new_head = (rec['yc'] - yc_pred) / dx
            if abs(new_head) <= 0.7:
                alpha = 0.5 if coast_run == 0 else 0.3
                head = (1 - alpha) * head + alpha * float(np.clip(new_head, -0.7, 0.7))
        yc_pred = rec['yc']
        x_prev = xmed
        if use_zb:
            zb_pred = float(zb_best)
            zb_hist.append((xmed, float(zb_best)))
            if len(zb_hist) >= 3:
                hx = np.array([t[0] for t in zb_hist[-6:]])
                hz = np.array([t[1] for t in zb_hist[-6:]])
                if hx.max() - hx.min() > 1.5:
                    g_tr = float(np.polyfit(hx, hz, 1)[0])
                    # blend tracked grade with range bootstrap (short
                    # baselines are noise-dominated)
                    span = hx.max() - hx.min()
                    w_tr = min(span / 6.0, 1.0)
                    grade = float(np.clip((1 - w_tr) * grade0 + w_tr * g_tr,
                                          -0.15, 0.15))
        coast_run = 0
        out.append(rec)
    # far candidates join the pool unvalidated; RANSAC in fit sorts out
    for rec in far_cands:
        rec['far'] = True
    for rec in out:
        rec['far'] = False
    out = sorted(out + far_cands, key=lambda r: r['x'])
    return out, grade0


def ransac_inliers(tracked):
    # RANSAC consensus for Yc stations: drop drift/junk stations (weak
    # fallback locks, bank locks) that no smooth curve explains together
    # with the majority. Model aX^2+bX^3 ridge-regularized; tol grows with
    # x. Returns inlier station list (falls back to all if no consensus).
    tr = [r for r in tracked if not r['coast']]
    n = len(tr)
    if n < 5:
        return tr
    xs = np.array([r['x'] for r in tr])
    ys = np.array([r['yc'] for r in tr])
    cs = np.array([r['contrast'] for r in tr])
    w = np.clip(cs / 0.06, 0.3, 2.0)
    lam_a = (0.03 / 0.008) ** 2
    lam_b = (0.03 / 2.5e-4) ** 2
    DL = np.diag([lam_a, lam_b])
    tol = 0.08 + 0.015 * xs
    best = None
    order = np.argsort(xs)
    tris = []
    for ii in range(n):
        for jj in range(ii + 1, n):
            for kk in range(jj + 1, n):
                i, j, k = order[ii], order[jj], order[kk]
                if xs[k] - xs[i] > 1.5:
                    tris.append((i, j, k))
    if not tris:
        return tr
    for (i, j, k) in tris:
        t3 = np.array([i, j, k])
        A3 = np.stack([xs[t3] ** 2, xs[t3] ** 3], axis=1)
        W3 = w[t3]
        AW = A3 * W3[:, None]
        M = AW.T @ A3 + DL
        try:
            ab = np.linalg.solve(M, AW.T @ (ys[t3] * W3))
        except np.linalg.LinAlgError:
            continue
        # physical caps: reject overfit triples (far leverage kills ridge)
        if abs(ab[0]) > 0.010 or abs(ab[1]) > 4e-4:
            continue
        res = np.abs(ys - (ab[0] * xs ** 2 + ab[1] * xs ** 3))
        inl = res <= tol
        if inl.sum() < 4:
            continue
        # trusted support: need >=2 high-contrast inliers
        if (cs[inl] >= 0.06).sum() < 2:
            continue
        score = w[inl].sum()
        err = (w[inl] * res[inl] ** 2).sum()
        key = (round(float(score), 6), -err)
        if best is None or key > best[0]:
            best = (key, inl)
    if best is None:
        return tr
    return [r for r, kk in zip(tr, best[1]) if kk]


def _ring_median_profile(p, Yc, zb_ref=-0.87):
    """Direct (x, z) ground profile: per-ring median of points near the
    centerline. No tracking/pairing; reaches x~26 (rings -15..-1)."""
    hxy = np.hypot(p[:, 0], p[:, 1])
    el = np.degrees(np.arctan2(p[:, 2], hxy))
    er = np.round(el).astype(int)
    xs, zs = [], []
    for e in range(-15, 0):
        m = er == e
        if m.sum() < 6:
            continue
        q = p[m]
        # gate around centerline at this ring's x (iterated once);
        # widen far: Z-medians tolerate Y-error (strip is Z-flat)
        x0 = float(np.median(q[:, 0]))
        yc = float(Yc(np.array([x0]))[0])
        hw = 0.50 + 0.06 * max(x0 - 8.0, 0.0)
        sel = (np.abs(q[:, 1] - yc) < hw) & (q[:, 2] > -1.8) & (q[:, 2] < 1.5)
        if sel.sum() < 4:
            continue
        x0 = float(np.median(q[sel, 0]))
        yc = float(Yc(np.array([x0]))[0])
        hw = 0.50 + 0.06 * max(x0 - 8.0, 0.0)
        sel = (np.abs(q[:, 1] - yc) < hw) & (q[:, 2] > -1.8) & (q[:, 2] < 1.5)
        if sel.sum() < 4:
            continue
        xs.append(float(np.median(q[sel, 0])))
        zs.append(float(np.median(q[sel, 2])))
    return np.array(xs), np.array(zs)


def ring_profile_detections(p, Zb):
    """Far lateral measurement, curve-immune: per ring (full 360deg arc, no
    az gate), select points near the strip level Zb(X) and find the bump
    (rail pairs preferred, plateau-contrast fallback). Returns Yc-only
    station dicts (zb fields nan)."""
    hxy = np.hypot(p[:, 0], p[:, 1])
    el = np.degrees(np.arctan2(p[:, 2], hxy))
    er = np.round(el).astype(int)
    out = []
    for e in range(-8, 0):
        m = er == e
        if m.sum() < 6:
            continue
        q = p[m]
        zbx = np.asarray(Zb(q[:, 0]), float)
        wdt = 0.08 + 0.008 * np.maximum(q[:, 0] - 10.0, 0.0)
        wdt = np.minimum(wdt, 0.25)
        dz = q[:, 2] - zbx
        g = q[np.abs(dz) < wdt]
        gdz = dz[np.abs(dz) < wdt]
        if len(g) < 8:
            continue
        # ---- rail pairs on the gated profile ----
        cand = (gdz > 0.02) & (gdz < 0.16)
        pairs = []
        if cand.sum() >= 2:
            order = np.argsort(g[:, 1])
            ys_all = g[:, 1][order]
            dz_all = gdz[order]
            is_c = cand[order]
            peaks = []
            for ii in np.where(is_c)[0]:
                nb = np.abs(ys_all - ys_all[ii])
                others = dz_all[(nb > 0.06) & (nb < 0.20)]
                if len(others) > 0 and dz_all[ii] <= np.median(others) + 0.020:
                    continue
                # rail heads are narrow in Z; wall columns spread >10cm
                col = dz_all[nb < 0.06]
                if len(col) >= 2 and (col.max() - col.min()) > 0.09:
                    continue
                peaks.append(ii)
            used = np.zeros(len(ys_all), bool)
            for ii in sorted(peaks, key=lambda k: -dz_all[k]):
                if used[ii]:
                    continue
                dy = np.abs(ys_all - ys_all[ii])
                ddz = np.abs(dz_all - dz_all[ii])
                pm = (~used) & (dy > 0.52) & (dy < 0.68) & (ddz < 0.045)
                pm[ii] = False
                cands = np.where(pm)[0]
                if len(cands) == 0:
                    continue
                jj = cands[np.argmin(ddz[cands])]
                yl, yh = min(ys_all[ii], ys_all[jj]), max(ys_all[ii], ys_all[jj])
                btw = dz_all[(ys_all > yl + 0.08) & (ys_all < yh - 0.08)]
                plvl = 0.5 * (dz_all[ii] + dz_all[jj])
                if len(btw) >= 1 and np.median(btw) < plvl - 0.015 and \
                        -0.06 <= np.median(btw) <= 0.03:
                    yc = 0.5 * (ys_all[ii] + ys_all[jj])
                    if abs(yc) < 4.0:
                        pairs.append((yc, plvl))
                        used[ii] = True
                        used[jj] = True
            if pairs:
                pairs.sort(key=lambda t: -t[1])
                yc = float(pairs[0][0])
                sel = np.abs(g[:, 1] - yc) < 0.5
                xe = float(np.median(g[sel, 0])) if sel.sum() >= 2 else \
                    float(np.median(q[:, 0]))
                if xe <= 12.0:
                    continue
                out.append({'x': xe, 'yc': yc, 'zb_strip': np.nan,
                            'zb_rail': np.nan, 'contrast': 0.09,
                            'n_cen': 6, 'coast': False, 'el': e,
                            'far': True})
                continue
        # ---- fallback: plateau bump contrast scan ----
        ylo, yhi = float(g[:, 1].min() + 1.6), float(g[:, 1].max() - 1.6)
        ylo, yhi = max(ylo, -4.0), min(yhi, 4.0)
        if yhi - ylo < 0.5:
            continue
        best = None
        yc = ylo
        while yc <= yhi + 1e-9:
            d = g[:, 1] - yc
            cen = gdz[np.abs(d) < 0.35]
            lf = gdz[(d > 0.80) & (d < 1.60)]
            rf = gdz[(d < -0.80) & (d > -1.60)]
            if len(cen) >= 4 and len(lf) >= 3 and len(rf) >= 3:
                spread = np.percentile(cen, 90) - np.percentile(cen, 10)
                if spread < 0.14:
                    cc = np.median(cen) - 0.5 * (np.median(lf) + np.median(rf))
                    if best is None or cc > best[0]:
                        best = (cc, yc)
            yc += 0.15
        if best is not None and best[0] > 0.025:
            yc = float(best[1])
            sel = np.abs(g[:, 1] - yc) < 0.5
            xe = float(np.median(g[sel, 0])) if sel.sum() >= 2 else \
                float(np.median(q[:, 0]))
            if xe <= 12.0:
                continue
            out.append({'x': xe, 'yc': yc, 'zb_strip': np.nan,
                        'zb_rail': np.nan, 'contrast': 0.06,
                        'n_cen': 4, 'coast': False, 'el': e, 'far': True})
    return out


def fit_models(tracked, grade0=0.0, p=None):
    """Fit Yc(X)=aX^2+bX^3 and Zb(X)=z0+gX+pX^2 (linear grade + mild
    curvature; no cubic -> no extrapolation dives). Grade prior centered
    at grade0 (range-derived secant). If points p given, ring-median
    profile augments Zb (far coverage to ~26m). Returns dict with coefs,
    xmax (last tracked), heading/curvature/grade at xmax, zb_bias."""
    inl = ransac_inliers(tracked)
    res = {'ok': False, 'n_in': len(inl)}
    xs = np.array([r['x'] for r in inl])
    ys = np.array([r['yc'] for r in inl])
    cs = np.array([r['contrast'] for r in inl])
    zb_s = np.array([r['zb_strip'] for r in inl])
    zb_r = np.array([r['zb_rail'] for r in inl])
    if len(xs) < 4:
        return res
    # --- Yc fit, weighted by contrast, Huber iterations, ridge prior ---
    w = np.clip(cs / 0.06, 0.3, 2.0)
    A = np.stack([xs ** 2, xs ** 3], axis=1)
    # ridge: a~N(0,siga), b~N(0,sigb) with noise scale ~3cm
    siga, sigb = 0.008, 2.5e-4
    ra = 0.03 / siga
    rb = 0.03 / sigb
    A_aug = np.vstack([A, [[ra, 0.0], [0.0, rb]]])
    a, b = 0.0, 0.0
    for _ in range(20):
        pred = A @ np.array([a, b])
        r = ys - pred
        s = 1.4826 * np.median(np.abs(r)) + 1e-6
        s = max(s, 0.02)
        u = np.abs(r) / (1.345 * s)
        hw = np.where(u < 1, 1.0, 1.0 / u)
        W = w * hw
        Aw = A_aug * np.concatenate([W, [1.0, 1.0]])[:, None]
        yw = np.concatenate([ys * W, [0.0, 0.0]])
        try:
            coef, *_ = np.linalg.lstsq(Aw, yw, rcond=None)
        except Exception:
            break
        if abs(coef[0] - a) < 1e-9 and abs(coef[1] - b) < 1e-9:
            a, b = coef
            break
        a, b = coef
    # --- Zb fit ---
    # calibrate strip offset from slices with rails
    both = ~np.isnan(zb_r) & ~np.isnan(zb_s)
    if both.sum() >= 2:
        off = np.median(zb_r[both] - zb_s[both])
        off = float(np.clip(off, -0.06, 0.10))
    else:
        off = 0.02
    has_r = ~np.isnan(zb_r)
    has_s = ~np.isnan(zb_s)
    keep = has_r | has_s
    if keep.sum() < 3:
        return res
    xmax_yc = float(xs.max())
    ntrack_yc = int(len(xs))
    xs_z = xs[keep]
    zobs = np.where(has_r[keep], zb_r[keep], zb_s[keep] + off)
    zw = np.where(has_r[keep], 4.0, 0.5) * np.clip(cs[keep] / 0.06, 0.3, 2.0)
    is_rail = has_r[keep]
    xs = xs_z
    g_prior = grade0
    # grade prior centered at long-baseline median grade (tight: short
    # baselines cannot measure grade); curvature mild
    sigg, sigp = 0.004, 2e-4
    rg = 0.02 / sigg
    rp = 0.02 / sigp
    # ring-median profile: dense far coverage (to ~26m), calibrated to rails
    if p is not None and len(p) > 100:
        _a, _b = float(a), float(b)
        Yc_g = lambda X: _a * np.asarray(X, float) ** 2 + _b * np.asarray(X, float) ** 3
        mx, mz = _ring_median_profile(p, Yc_g)
        if len(mx) >= 4:
            # calibrate median-vs-rail bias on near overlap (x<9)
            near = mx < 9.0
            if near.sum() >= 2 and is_rail.sum() >= 2:
                cal = []
                for xi, zi in zip(mx[near], mz[near]):
                    dd = np.abs(xs[is_rail] - xi)
                    if dd.min() < 1.2:
                        cal.append(zobs[is_rail][np.argmin(dd)] - zi)
                moff = float(np.median(cal)) if len(cal) >= 2 else 0.0
                moff = float(np.clip(moff, -0.10, 0.10))
            else:
                moff = 0.0
            mz = mz + moff
            # grade prior center from medians (long-baseline truth; secant
            # grade0 is wrong on vertical curves)
            g_prior = grade0
            if len(mx) >= 5 and mx.max() - mx.min() > 5.0:
                gm, cm = 0.0, float(np.median(mz))
                for _ in range(10):
                    rr = mz - (gm * mx + cm)
                    s = max(1.4826 * np.median(np.abs(rr)), 0.010)
                    u = np.abs(rr) / (1.345 * s)
                    W = np.where(u < 1, 1.0, np.divide(1.0, np.maximum(u, 1e-9)))
                    Gm = np.stack([mx, np.ones_like(mx)], axis=1)
                    try:
                        gm, cm = np.linalg.lstsq(
                            Gm * W[:, None], mz * W, rcond=None)[0]
                    except Exception:
                        break
                g_prior = float(np.clip(gm, -0.10, 0.10))
            # two-stage gate: keep medians near the station-only fit
            # (loose far: station fit may miss grades)
            z0s, gs, ps = -0.85, g_prior, 0.0
            Bs = np.stack([np.ones_like(xs), xs, xs ** 2], axis=1)
            for _ in range(10):
                rr = zobs - Bs @ np.array([z0s, gs, ps])
                s = max(1.4826 * np.median(np.abs(rr)), 0.010)
                u = np.abs(rr) / (1.345 * s)
                W = zw * np.where(u < 1, 1.0, 1.0 / u)
                Ba = np.vstack([Bs, [[0.0, rg, 0.0], [0.0, 0.0, rp]]])
                Bw = Ba * np.concatenate([W, [1.0, 1.0]])[:, None]
                yw = np.concatenate([zobs * W, [rg * g_prior, 0.0]])
                try:
                    z0s, gs, ps = np.linalg.lstsq(Bw, yw, rcond=None)[0]
                except Exception:
                    break
            gate = 0.10 + 0.030 * mx
            mkeep = np.abs(mz - (z0s + gs * mx + ps * mx ** 2)) <= gate
            if mkeep.sum() >= 3:
                xs = np.concatenate([xs, mx[mkeep]])
                zobs = np.concatenate([zobs, mz[mkeep]])
                zw = np.concatenate([zw, np.full(mkeep.sum(), 1.2)])
    B = np.stack([np.ones_like(xs), xs, xs ** 2], axis=1)
    B_aug = np.vstack([B, [[0.0, rg, 0.0], [0.0, 0.0, rp]]])
    z0, gg, pp = -0.85, g_prior, 0.0
    # rail zb precision is ~7mm; tight floor -> hard outlier rejection
    for _ in range(20):
        pred = B @ np.array([z0, gg, pp])
        r = zobs - pred
        s = 1.4826 * np.median(np.abs(r)) + 1e-6
        s = max(s, 0.008)
        u = np.abs(r) / (1.345 * s)
        hw = np.where(u < 1, 1.0, 1.0 / u)
        W = zw * hw
        Bw = B_aug * np.concatenate([W, [1.0, 1.0]])[:, None]
        yw = np.concatenate([zobs * W, [rg * g_prior, 0.0]])
        try:
            coef, *_ = np.linalg.lstsq(Bw, yw, rcond=None)
        except Exception:
            break
        if np.max(np.abs(coef - np.array([z0, gg, pp]))) < 1e-9:
            z0, gg, pp = coef
            break
        z0, gg, pp = coef
    # post-hoc hard clip: drop zb stations >3.5cm off, refit once
    r = zobs - B @ np.array([z0, gg, pp])
    keepz = np.abs(r) <= 0.035
    if keepz.sum() >= 3 and (~keepz).sum() > 0:
        Bk = B[keepz]
        zk = zobs[keepz]
        Wk = zw[keepz]
        Bk_aug = np.vstack([Bk, [[0.0, rg, 0.0], [0.0, 0.0, rp]]])
        Bw = Bk_aug * np.concatenate([Wk, [1.0, 1.0]])[:, None]
        yw = np.concatenate([zk * Wk, [rg * g_prior, 0.0]])
        try:
            coef, *_ = np.linalg.lstsq(Bw, yw, rcond=None)
            z0, gg, pp = coef
        except Exception:
            pass
    xmax = max(xmax_yc, float(xs.max()))
    res.update(ok=True, a=float(a), b=float(b), z0=float(z0), g=float(gg),
               p=float(pp), xmax=xmax, off=off, ntrack=ntrack_yc,
               ntrack_z=int(len(xs)))
    return res


def centerline_funcs(fit):
    """Return Yc(X), Zb(X), theta(X) callables (X-frame, valid to xmax).
    Extension handled by build_polyline."""
    a, b = fit['a'], fit['b']
    z0, g, p = fit['z0'], fit['g'], fit['p']
    xm = fit['xmax']

    def Yc(X):
        X = np.atleast_1d(np.asarray(X, float))
        return a * X ** 2 + b * X ** 3

    def Zb(X):
        X = np.atleast_1d(np.asarray(X, float))
        return z0 + g * X + p * X ** 2

    def Theta(X):
        X = np.atleast_1d(np.asarray(X, float))
        return np.arctan(2 * a * X + 3 * b * X ** 2)

    return Yc, Zb, Theta


def build_polyline(fit, tracked):
    """Centerline polyline: columns X, Y, Zb, theta. Extends beyond xmax by
    clothoid integration from LOCAL end state (robust), capped at |theta|<=80.
    Returns (P,) arrays."""
    a, b = fit['a'], fit['b']
    z0, g, p = fit['z0'], fit['g'], fit['p']
    xm = fit['xmax']
    # within-data part: poly sampled every 0.5m
    Xs = np.arange(0.0, xm + 0.251, 0.5)
    Ys = a * Xs ** 2 + b * Xs ** 3
    Zs = z0 + g * Xs + p * Xs ** 2
    Th = np.arctan(2 * a * Xs + 3 * b * Xs ** 2)
    # local end state from last stations (Huber-robust: junk stations like
    # weak-contrast drift must not steer the extension heading)
    tr = [r for r in tracked if not r['coast']]
    if len(tr) >= 4:
        last = tr[-min(6, len(tr)):]
        lx = np.array([r['x'] for r in last])
        ly = np.array([r['yc'] for r in last])
        lw = np.clip(np.array([r['contrast'] for r in last]) / 0.06, 0.3, 2.0)
        try:
            L = np.stack([lx ** 2, lx, np.ones_like(lx)], axis=1)
            c2, c1, c0 = np.polyfit(lx, ly, 2, w=lw)
            for _ in range(15):
                rr = ly - L @ np.array([c2, c1, c0])
                s = max(1.4826 * np.median(np.abs(rr)), 0.030)
                u = np.abs(rr) / (1.345 * s)
                hw = np.where(u < 1, 1.0, 1.0 / u)
                W = lw * hw
                coef, *_ = np.linalg.lstsq(L * W[:, None], ly * W, rcond=None)
                if np.max(np.abs(coef - np.array([c2, c1, c0]))) < 1e-9:
                    c2, c1, c0 = coef
                    break
                c2, c1, c0 = coef
            th_m = float(np.arctan(c1 + 2 * c2 * xm))
            kap_m = float(2 * c2 / (1 + (c1 + 2 * c2 * xm) ** 2) ** 1.5)
        except Exception:
            th_m = float(Th[-1])
            d1 = 2 * a * xm + 3 * b * xm ** 2
            kap_m = float((2 * a + 6 * b * xm) / (1 + d1 ** 2) ** 1.5)
    else:
        th_m = float(Th[-1])
        d1 = 2 * a * xm + 3 * b * xm ** 2
        kap_m = float((2 * a + 6 * b * xm) / (1 + d1 ** 2) ** 1.5)
    # trust: shrink weak curvature toward 0 (straight prior far)
    w_trust = float(min(abs(kap_m) / 0.009, 1.0))
    kap0 = kap_m * (0.25 + 0.75 * w_trust)
    # clothoid rate from global cubic (shrunk: half, for stability)
    kap1 = float(6 * b * 0.5)
    kap1 = float(np.clip(kap1, -0.004, 0.004))
    ym = float(Ys[-1])
    zm = float(Zs[-1])
    gr = float(np.clip(g + 2 * p * xm, -0.10, 0.10))
    # integrate extension
    ds = 0.5
    ex, ey, ez, et = [xm], [ym], [zm], [th_m]
    th = th_m
    for i in range(1, 160):
        s = i * ds
        kap = kap0 + kap1 * s
        kap = float(np.clip(kap, -0.12, 0.12))
        th = th + kap * ds
        if abs(th) > np.radians(80):
            break
        nx = ex[-1] + np.cos(th) * ds
        ny = ey[-1] + np.sin(th) * ds
        if nx > 63 or nx < ex[-1] - 0.01:
            break
        ex.append(nx)
        ey.append(ny)
        ez.append(zm + gr * s)
        et.append(th)
    Xp = np.concatenate([Xs, np.array(ex[1:])])
    Yp = np.concatenate([Ys, np.array(ey[1:])])
    Zp = np.concatenate([Zs, np.array(ez[1:])])
    Tp = np.concatenate([Th, np.array(et[1:])])
    return Xp, Yp, Zp, Tp


# S-optimal operating point (val grid): tight near gate + clip confirmation
GATE_LAT = 0.55
GATE_ZBOT = 0.36
GATE_ZTOP = 1.15
GATE_XCAP = 13.0
# v2 tiers (offline val S=0.36144): near-low band for low objects,
# far tier for mid-range recall
GATE_XNEAR = 7.0
GATE_ZLOW = 0.18
GATE_XFAR1 = 15.0
GATE_LATFAR = 0.35
GATE_ZBFAR = 0.55
CLIP_MIN = 15
# near confirmation: clip also needs >= CONFIRM_N points at X <= CONFIRM_X
CONFIRM_X = 11.0
CONFIRM_N = 8


def _default_fit(p):
    """Fallback geometry when tracking fails (e.g., giant occluder covering
    the near track): straight centerline, strip level = lowest of near
    X-windows (strip is the lowest surface; objects sit above it)."""
    zb_ref = -0.87
    try:
        cands = []
        for x0, x1 in ((1.5, 2.5), (2.5, 3.5), (3.5, 4.5)):
            m = (p[:, 0] > x0) & (p[:, 0] < x1) & (np.abs(p[:, 1]) < 0.28) & \
                (p[:, 2] > -1.2) & (p[:, 2] < -0.5)
            if m.sum() >= 8:
                cands.append(float(np.median(p[m, 2])))
        if cands:
            zb_ref = min(cands)
    except Exception:
        pass
    try:
        g0 = float(np.clip(_estimate_grade0(p, zb_ref), -0.05, 0.05))
    except Exception:
        g0 = 0.0
    return {'ok': True, 'a': 0.0, 'b': 0.0, 'z0': zb_ref - g0 * 3.0,
            'g': g0, 'p': 0.0, 'xmax': 12.0, 'off': 0.02, 'ntrack': 0,
            'ntrack_z': 0, 'default': True}


def predict_mask(p, zb_bias=-0.02):
    """Full per-frame prediction. Returns (mask uint8, info dict)."""
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
        info['n_prof'] = 0
    else:
        # far lateral pass: ring-profile detections gated by Zb0
        # (curve-immune)
        z0, gg, pp = fit0['z0'], fit0['g'], fit0['p']
        Zb0 = lambda X: z0 + gg * np.asarray(X, float) + pp * np.asarray(X, float) ** 2
        try:
            prof = ring_profile_detections(p, Zb0)
        except Exception:
            prof = []
        info['n_prof'] = len(prof)
        allst = tracked + prof
        fit = fit_models(allst, grade0, p)
        if not fit.get('ok'):
            fit = fit0
            allst = tracked
    inl = ransac_inliers(allst)
    info['n_in'] = len(inl)
    Xp, Yp, Zp, Tp = build_polyline(fit, inl)
    # perpendicular projection: nearest vertex (0.5m spacing: sagitta ~2mm)
    dx = p[:, 0:1] - Xp[None, :]
    dy = p[:, 1:2] - Yp[None, :]
    d2 = dx * dx + dy * dy
    j = np.argmin(d2, axis=1)
    # signed lateral via segment direction
    j2 = np.minimum(j + 1, len(Xp) - 1)
    j1 = np.maximum(j - 1, 0)
    tx = Xp[j2] - Xp[j1]
    ty = Yp[j2] - Yp[j1]
    n = np.hypot(tx, ty) + 1e-12
    lat = (-(p[:, 0] - Xp[j]) * ty + (p[:, 1] - Yp[j]) * tx) / n
    zb = Zp[j] + zb_bias
    zrel = p[:, 2] - zb
    alat = np.abs(lat)
    X = p[:, 0]
    # tier 1: base box (must match offline_search.score exactly)
    inside = (alat <= GATE_LAT + 1e-9) & \
        (zrel >= GATE_ZBOT - 1e-9) & (zrel <= GATE_ZTOP + 1e-9) & \
        (X > -1.0) & (X <= GATE_XCAP + 1e-9)
    # tier 2: near-low band (low objects, rails excluded by ZLOW)
    inside = inside | ((X <= GATE_XNEAR + 1e-9) & (alat <= GATE_LAT + 1e-9) &
                       (zrel >= GATE_ZLOW - 1e-9) & (zrel <= GATE_ZTOP + 1e-9) &
                       (X > -1.0))
    # tier 3: far tier (mid-range recall, tight lat/high zbot)
    inside = inside | ((X > GATE_XCAP + 1e-9) & (X <= GATE_XFAR1 + 1e-9) &
                       (alat <= GATE_LATFAR + 1e-9) &
                       (zrel >= GATE_ZBFAR - 1e-9) &
                       (zrel <= GATE_ZTOP + 1e-9))
    info.update(fit)
    return inside.astype(np.uint8), info
