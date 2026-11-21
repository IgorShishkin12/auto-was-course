"""v3 calibration grid on train/val labels. Run when gate_*.npz land.

Stage A: veto safety (train+val): each veto alone vs v2 baseline.
Stage B: joint grid around winners × CN x CFMIN.
Prints S/R/P/F tables; saves results to grid_v3_results.txt.
"""
import sys
import itertools
import numpy as np
sys.path.insert(0, '/home/user')
from offline_search import load, show
from v3_search import score_v3

BASE = dict(CMIN=15, CX=11.0, CN=8)


PATHS = {'train': ('train_units.npz', 'train_posframes.npz'),
         'val': ('units_val.npz', 'posframes_val.npz')}


def run(split):
    u, p = PATHS[split]
    D = load(f'gate_{split}.npz', u, p)
    out = []

    def ev(name, **kw):
        p = dict(BASE)
        p.update(kw)
        d = score_v3(D, **p)
        out.append((name, p, d))
        print(f'{split} {name}: S={d["S"]:.5f} R={d["R"]:.4f} '
              f'Rg={[round(x, 3) for x in d["Rg"]]} P={d["P"]:.4f} '
              f'F={d["F"]:.5f} nFA={d["nFA"]} nfr={d["nselfr"]}',
              flush=True)
        return d

    print(f'===== {split}: baseline =====', flush=True)
    ev('v2_baseline')
    print(f'===== {split}: single vetoes =====', flush=True)
    ev('VX2.0', VXRANGE=2.0)
    ev('VX3.0', VXRANGE=3.0)
    ev('FMIN4', FMIN=4)
    ev('FMIN6', FMIN=6)
    ev('CFMIN2', CFMIN=2)
    ev('CFMIN3', CFMIN=3)
    ev('JLAT.5', VJLAT=0.5)
    ev('JLAT.4', VJLAT=0.4)
    ev('JX1.5', VJX=1.5)
    ev('JX2.0', VJX=2.0)
    ev('VL1.0', VLRANGE=1.0)
    ev('VREC2', VREC=2.0)
    ev('CN0', CN=0)
    ev('CN4', CN=4)
    ev('CN2', CN=2)
    ev('CM10', CMIN=10)
    ev('CM10CN0', CMIN=10, CN=0)
    ev('CM20', CMIN=20)
    return out


def run_joint(split):
    u, p = PATHS[split]
    D = load(f'gate_{split}.npz', u, p)
    print(f'===== {split}: joint grid =====', flush=True)
    rows = []
    for vx, fm, jl, jx, cf, cn in itertools.product(
            [2.0, 0.0], [4, 0], [0.5, 0.0], [1.5, 0.0],
            [2, 0], [0, 8]):
        p = dict(BASE, VXRANGE=vx, FMIN=fm, VJLAT=jl, VJX=jx,
                 CFMIN=cf, CN=cn)
        d = score_v3(D, **p)
        rows.append((d['S'], dict(p), d))
        print(f'{split} vx={vx} fm={fm} jl={jl} jx={jx} cf={cf} cn={cn}: '
              f'S={d["S"]:.5f} R={d["R"]:.4f} P={d["P"]:.4f} '
              f'F={d["F"]:.5f} nFA={d["nFA"]}', flush=True)
    rows.sort(key=lambda t: -t[0])
    print(f'===== {split}: TOP 10 =====', flush=True)
    for s, p, d in rows[:10]:
        print(f'S={s:.5f} R={d["R"]:.4f} P={d["P"]:.4f} F={d["F"]:.5f} '
              f'nFA={d["nFA"]} {p}', flush=True)
    return rows


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    with open('grid_v3_results.txt', 'a') as fo:
        pass
    if which in ('all', 'single'):
        run('val')
        run('train')
    if which in ('all', 'joint'):
        run_joint('val')
        run_joint('train')
