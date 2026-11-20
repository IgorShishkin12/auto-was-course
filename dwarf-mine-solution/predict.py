"""Run gauge prediction over a dataset split -> packed .bin + diagnostics.

Per-frame tight near gate (see tracklib GATE_*), then clip confirmation:
clips (10 consecutive frames) with < CLIP_MIN selected points, or without
near confirmation (< CONFIRM_N points at X <= CONFIRM_X), are zeroed.
"""
import sys, os, glob, time
import numpy as np
sys.path.insert(0, '/home/user')
from tracklib import predict_mask, CLIP_MIN, CONFIRM_X, CONFIRM_N

def main(dataroot, outbin, diagpath=None, limit=None):
    files = sorted(glob.glob(os.path.join(dataroot, '*.npz')))
    if limit:
        files = files[:limit]
    masks = []
    t0 = time.time()
    diag = []
    for fi, f in enumerate(files):
        d = np.load(f)
        pts = d['points']; off = d['frame_offsets']
        T = len(off) - 1
        has_lab = 'labels' in d
        lab = d['labels'] if has_lab else None
        fmasks = []
        infos = []
        n_conf = []
        for k in range(T):
            p = pts[off[k]:off[k + 1]]
            m, info = predict_mask(p)
            fmasks.append(m)
            infos.append(info)
            n_conf.append(int(((m == 1) & (p[:, 0] <= CONFIRM_X)).sum()))
        # clip confirmation: zero clips with < CLIP_MIN points, or without
        # near confirmation (< CONFIRM_N points at X <= CONFIRM_X)
        for c in range((T + 9) // 10):
            idx = list(range(c * 10, min((c + 1) * 10, T)))
            tot = sum(int(fmasks[k].sum()) for k in idx)
            tot_c = sum(n_conf[k] for k in idx)
            if tot < CLIP_MIN or tot_c < CONFIRM_N:
                for k in idx:
                    fmasks[k] = np.zeros_like(fmasks[k])
        for k in range(T):
            m = fmasks[k]
            masks.append(m)
            if diagpath is not None and has_lab:
                l = lab[off[k]:off[k + 1]]
                tp = int(((m == 1) & (l == 1)).sum())
                fp = int(((m == 1) & (l == 0)).sum())
                fn = int(((m == 0) & (l == 1)).sum())
                fpx = ''
                if fp:
                    fx = pts[off[k]:off[k + 1]][(m == 1) & (l == 0), 0]
                    fpx = f'{fx.min():.1f}-{fx.max():.1f}'
                info = infos[k]
                diag.append(f'{os.path.basename(f)} {k} TP={tp} FP={fp} FN={fn} '
                            f'FPX={fpx} ' +
                            ' '.join(f'{kk}={vv:.4f}' if isinstance(vv, float) else f'{kk}={vv}'
                                      for kk, vv in info.items() if kk != 'ok'))
        if (fi + 1) % 5 == 0:
            print(f'{fi+1}/{len(files)} {time.time()-t0:.0f}s', flush=True)
    allm = np.concatenate(masks)
    np.packbits(allm, bitorder='little').tofile(outbin)
    print(f'wrote {outbin}: {len(allm)} bits')
    if diagpath is not None:
        with open(diagpath, 'w') as fo:
            fo.write('\n'.join(diag))
        print(f'wrote {diagpath}: {len(diag)} frames')

if __name__ == '__main__':
    dataroot, outbin = sys.argv[1], sys.argv[2]
    diag = sys.argv[3] if len(sys.argv) > 3 else None
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
    main(dataroot, outbin, diag, limit)
