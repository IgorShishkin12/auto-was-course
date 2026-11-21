"""v3 production predictor: v2 gate (tracklib constants) + frame vetoes
+ clip confirm + clip motion veto. Mirrors v3_search.score_v3 exactly
(gate fixed at v2 values; veto/confirm params via CLI).

Usage: python3 predict_v3.py <dataroot> <outbin> [diag] [limit] [k=v ...]
Params: CMIN CX CN FMIN CFMIN VXRANGE VLRANGE VYRANGE VXMIN VRING_N
        VRING_X VETOZ0 Z0FRAC VJLAT VJX VREC
"""
import sys
import os
import glob
import time
import numpy as np
sys.path.insert(0, '/home/user')
from tracklib import predict_mask
from vetolib import frame_veto, clip_motion_ok

P = dict(CMIN=15, CX=11.0, CN=8, FMIN=0, CFMIN=0,
         VXRANGE=0.0, VLRANGE=0.0, VYRANGE=0.0, VXMIN=5.0, VXNEAR=0.0,
         VRING_N=0, VRING_X=0.0, VETOZ0=0, Z0FRAC=0.0,
         VJLAT=0.0, VJX=0.0, VREC=0.0, FMOTION=0, FARBIG=0, VJN=1,
         VJNF=0)


def main(dataroot, outbin, diagpath=None, limit=None):
    files = sorted(glob.glob(os.path.join(dataroot, '*.npz')))
    if limit:
        files = files[:limit]
    masks = []
    t0 = time.time()
    diag = []
    for fi, f in enumerate(files):
        d = np.load(f)
        pts = d['points']
        off = d['frame_offsets']
        T = len(off) - 1
        has_lab = 'labels' in d
        lab = d['labels'] if has_lab else None
        fmasks = []
        infos = []
        fxmin = []
        flatm = []
        fcn = []
        for k in range(T):
            p = pts[off[k]:off[k + 1]]
            m, info, lat, zrel = predict_mask(p, ret_arrays=True)
            m = m.astype(bool)
            if P['VETOZ0']:
                m = m & (p[:, 2] != 0.0)
            if m.any() and (P['VXRANGE'] > 0 or P['VLRANGE'] > 0 or
                            P['VYRANGE'] > 0 or P['VRING_N'] > 0 or P['VXNEAR'] > 0 or
                            P['Z0FRAC'] > 0 or P['FMIN'] > 0):
                ms = np.nonzero(m)[0]
                if frame_veto(p[ms, 0], p[ms, 1], p[ms, 2], lat[ms],
                              VXRANGE=P['VXRANGE'], VLRANGE=P['VLRANGE'],
                              VYRANGE=P['VYRANGE'], VXMIN=P['VXMIN'], VXNEAR=P['VXNEAR'],
                              VRING_N=P['VRING_N'], VRING_X=P['VRING_X'],
                              Z0FRAC=P['Z0FRAC'], FMIN=P['FMIN']):
                    m = np.zeros_like(m)
            fmasks.append(m)
            infos.append(info)
            if m.any():
                ms = np.nonzero(m)[0]
                fxmin.append(float(p[ms, 0].min()))
                flatm.append(float(lat[ms].mean()))
                fcn.append(int(m.sum()))
            else:
                fxmin.append(np.inf)
                flatm.append(0.0)
                fcn.append(0)
        # clip-level decisions
        for c in range((T + 9) // 10):
            idx = list(range(c * 10, min((c + 1) * 10, T)))
            tot = sum(int(fmasks[k].sum()) for k in idx)
            kill = tot < P['CMIN']
            if not kill and P['CN'] > 0:
                near = 0
                for k in idx:
                    if fmasks[k].any():
                        pk = pts[off[k]:off[k + 1]]
                        near += int(((fmasks[k]) & (pk[:, 0] <= P['CX'])).sum())
                if near < P['CN'] and \
                        not (P['FARBIG'] > 0 and tot >= P['FARBIG']):
                    kill = True
            selfr = [k for k in idx if fmasks[k].any()]
            if not kill and P['CFMIN'] > 0 and len(selfr) < P['CFMIN']:
                kill = True
            if not kill and (P['VJLAT'] > 0 or P['VJX'] > 0 or P['VREC'] > 0):
                if not clip_motion_ok(selfr,
                                      [fxmin[k] for k in selfr],
                                      [flatm[k] for k in selfr],
                                      [fcn[k] for k in selfr],
                                      FMOTION=P['FMOTION'],
                                      VJLAT=P['VJLAT'], VJX=P['VJX'],
                                      VREC=P['VREC'], VJN=P['VJN'],
                                      VJNF=P['VJNF']):
                    kill = True
            if kill:
                for k in idx:
                    fmasks[k] = np.zeros_like(fmasks[k])
        for k in range(T):
            m = fmasks[k].astype(np.uint8)
            masks.append(m)
            if diagpath is not None and has_lab:
                l = lab[off[k]:off[k + 1]]
                tp = int(((m == 1) & (l == 1)).sum())
                fp = int(((m == 1) & (l == 0)).sum())
                fn = int(((m == 0) & (l == 1)).sum())
                info = infos[k]
                diag.append(f'{os.path.basename(f)} {k} TP={tp} FP={fp} FN={fn} ' +
                            ' '.join(f'{kk}={vv:.4f}' if isinstance(vv, float) else f'{kk}={vv}'
                                      for kk, vv in info.items() if kk != 'ok'))
        if (fi + 1) % 5 == 0:
            print(f'{fi+1}/{len(files)} {time.time()-t0:.0f}s', flush=True)
    allm = np.concatenate(masks)
    np.packbits(allm, bitorder='little').tofile(outbin)
    print(f'wrote {outbin}: {len(allm)} bits')


if __name__ == '__main__':
    for a in sys.argv[5:]:
        k, v = a.split('=')
        P[k] = float(v) if '.' in v or 'e' in v.lower() else int(v)
    print('v3 params:', P, flush=True)
    dataroot, outbin = sys.argv[1], sys.argv[2]
    diag = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != '-' else None
    limit = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != '-' else None
    main(dataroot, outbin, diag, limit)
