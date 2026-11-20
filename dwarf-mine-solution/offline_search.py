"""Offline operating-point search on gate_val_wide.npz.

Replicates evaluate.py exactly (clips per file, 10 frames; units
(fi,clip,obj,grp); R/P/F/S) for any gate expressible via per-point
(lat, zrel, X): base box + optional near-low band + clip confirmation.
"""
import sys
import numpy as np

WIDE = dict(lat=0.70, zlo=0.10, zhi=1.50, xmax=25.0)


def load(path='gate_val_wide.npz', units='units_val.npz', pos='posframes_val.npz'):
    g = np.load(path)
    recs = g['recs']
    fr = g['frames']  # indexed by gf: (fi, k, n)
    u = np.load(units)
    ukeys = u['keys']  # (99,4): fi, clip, obj, grp
    un = u['n'].astype(int)
    p = np.load(pos)['pos']  # (606,2): fi, k
    F = len(fr)
    fi_of = fr['fi'].astype(int)
    k_of = fr['k'].astype(int)
    # clip index 0..C-1
    nfiles = int(fi_of.max()) + 1
    tpf = np.zeros(nfiles, int)
    for fi in range(nfiles):
        tpf[fi] = int((k_of[fi_of == fi]).max()) + 1
    cpf = tpf // 10
    coff = np.zeros(nfiles + 1, int)
    coff[1:] = np.cumsum(cpf)
    clip_of = coff[fi_of] + k_of // 10
    C = int(coff[-1])
    # (fi,k) -> gf
    gflut = dict(((int(fi_of[i]), int(k_of[i])), i) for i in range(F))
    pos_gf = np.array([gflut[(int(a), int(b))] for a, b in p])
    is_pos_frame = np.zeros(F, bool)
    is_pos_frame[pos_gf] = True
    # opportunity clips: >=1 empty frame
    has_empty = np.zeros(C, bool)
    np.logical_or.at(has_empty, clip_of[~is_pos_frame], True)
    opp = np.nonzero(has_empty)[0]
    # units: remap clip
    uk = [(int(a), int(coff[int(a)] + int(b)), int(c), int(d)) for a, b, c, d in ukeys]
    unit_lut = {(fi, c, o, gr): i for i, (fi, c, o, gr) in enumerate(uk)}
    ugrp = np.array([t[3] for t in uk])
    uclip = np.array([t[1] for t in uk])
    return dict(recs=recs, F=F, C=C, fi_of=fi_of, k_of=k_of, clip_of=clip_of,
                is_pos_frame=is_pos_frame, opp=opp, unit_lut=unit_lut,
                ugrp=ugrp, uclip=uclip, un=un)


def score(D, LAT=0.55, ZBOT=0.36, ZTOP=1.15, XCAP=12.0,
          CMIN=15, CX=11.0, CN=8, XNEAR=0.0, ZLOW=0.0,
          XF1=0.0, LATF=0.40, ZBF=0.36):
    """Return dict R,P,F,S + aux. XNEAR/ZLOW>0 enables near-low band;
    XF1>0 enables far tier (XCAP,XF1] with LATF/ZBF."""
    assert LAT <= WIDE['lat'] + 1e-9 and ZBOT >= WIDE['zlo'] - 1e-9 \
        and ZTOP <= WIDE['zhi'] + 1e-9 and XCAP <= WIDE['xmax'] + 1e-9, \
        'point outside wide collection'
    r = D['recs']
    lat = np.abs(r['lat'])
    z = r['zrel']
    X = r['X']
    sel = (lat <= LAT + 1e-9) & (z >= ZBOT - 1e-9) & (z <= ZTOP + 1e-9) & \
        (X > -1.0) & (X <= XCAP + 1e-9)
    if XNEAR > 0 and ZLOW > 0:
        assert ZLOW >= WIDE['zlo'] - 1e-9
        sel = sel | ((X <= XNEAR + 1e-9) & (lat <= LAT + 1e-9) &
                     (z >= ZLOW - 1e-9) & (z <= ZTOP + 1e-9) & (X > -1.0))
    if XF1 > 0:
        assert XF1 <= WIDE['xmax'] + 1e-9 and LATF <= WIDE['lat'] + 1e-9
        sel = sel | ((X > XCAP + 1e-9) & (X <= XF1 + 1e-9) &
                     (lat <= LATF + 1e-9) & (z >= ZBF - 1e-9) &
                     (z <= ZTOP + 1e-9))
    F, C = D['F'], D['C']
    gf = r['gf'].astype(int)
    isTP = r['obj'] >= 0
    # clip confirmation
    clip_of = D['clip_of']
    gsel = gf[sel]
    tot = np.bincount(clip_of[gsel], minlength=C)
    near = np.bincount(clip_of[gsel[X[sel] <= CX + 1e-9]], minlength=C)
    dead = (tot < CMIN) | (near < CN)
    if dead.any():
        dead_gf = dead[clip_of]
        keep = sel.copy()
        # zero recs in dead clips
        idx = np.nonzero(sel)[0]
        drop = dead_gf[gf[idx]]
        keep[idx[drop]] = False
        sel = keep
    gsel = gf[sel]
    selcnt = np.bincount(gsel, minlength=F)
    tpsel = sel & isTP
    tpcnt = np.bincount(gf[tpsel], minlength=F)
    # precision
    w = selcnt > 0
    P = float((tpcnt[w] / selcnt[w]).mean()) if w.any() else 0.0
    # unit hits
    if tpsel.any():
        go = gf[tpsel]
        co = clip_of[go]
        oo = r['obj'][tpsel].astype(int)
        gr = r['grp'][tpsel].astype(int)
        key = (co.astype(np.int64) * 9000000 + oo.astype(np.int64)) * 4 + gr
        ukey = np.unique(np.stack([key, go], axis=1), axis=0)
        hits = np.zeros(len(D['un']), int)
        lut = D['unit_lut']
        # invert: iterate unique (clip,obj,grp,gf)
        from collections import defaultdict
        per = defaultdict(set)
        for kk, gg in ukey:
            gg = int(gg)
            kk = int(kk)
            grr = kk % 4
            kk //= 4
            oo = kk % 9000000
            cc = kk // 9000000
            # need fi: from clip->fi via any frame; use stored uclip match
            per[(cc, oo, grr)].add(gg)
        # map (clip,obj,grp)->unit idx (fi implicit in clip)
        uidx = {}
        for (fi, c, o, gr), i in lut.items():
            uidx[(c, o, gr)] = i
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
    # false alarms: selections on EMPTY frames only (evaluate.py adds FA
    # iff the frame is empty AND selected; TP on positive frames of a
    # mixed clip is free)
    egsel = gsel[~D['is_pos_frame'][gsel]]  # selected recs on empty frames
    csel_e = np.bincount(clip_of[egsel], minlength=C) > 0 if len(egsel) \
        else np.zeros(C, bool)
    FA = np.nonzero(csel_e)[0]
    Ff = len(FA) / len(D['opp']) if len(D['opp']) else 0.0
    S = Rmean * P * (1 - Ff) ** 2
    return dict(R=Rmean, Rg=R, P=P, F=Ff, S=S, nFA=len(FA),
                nsel=int(sel.sum()), nselfr=int(w.sum()))


def show(name, d):
    print(f'{name}: R={d["R"]:.4f} {str([round(x,3) for x in d["Rg"]]):22s} '
          f'P={d["P"]:.4f} F={d["F"]:.5f} FA={d["nFA"]:3d} '
          f'S={d["S"]:.5f} nsel={d["nsel"]}')


if __name__ == '__main__':
    D = load()
    print(f'frames={D["F"]} clips={D["C"]} opps={len(D["opp"])} '
          f'units={len(D["un"])} recs={len(D["recs"])}')
    r = D['recs']
    print('obj<0 frac:', float((r["obj"] < 0).mean()),
          '| TP grp set:', sorted(set(r["grp"][r["obj"] >= 0].tolist())),
          '| FP grp set:', sorted(set(r["grp"][r["obj"] < 0].tolist())))
    base = dict()
    show('v1-point', score(D, **base))
