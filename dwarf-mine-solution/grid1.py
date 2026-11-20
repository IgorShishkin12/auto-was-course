"""Stage-1 offline grid: 1D sweeps + near-low band around v1+fallback."""
import sys
sys.path.insert(0, '/home/user')
from offline_search import load, score, show

D = load()
BASE = dict(LAT=0.55, ZBOT=0.36, ZTOP=1.15, XCAP=12.0, CMIN=15, CX=11.0, CN=8)
show('BASE', score(D, **BASE))

sweeps = dict(
    ZBOT=[0.28, 0.30, 0.32, 0.34, 0.36, 0.38, 0.40],
    LAT=[0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
    XCAP=[12.0, 13.0, 14.0, 15.0, 18.0],
    ZTOP=[1.00, 1.15, 1.30, 1.50],
    CMIN=[8, 10, 12, 15, 18, 22],
    CN=[4, 5, 6, 8, 10],
    CX=[10.0, 11.0, 12.0],
)
for k, vals in sweeps.items():
    for v in vals:
        p = dict(BASE)
        p[k] = v
        show(f'{k}={v}', score(D, **p))

print('--- near-low band ---')
for xn in (4.0, 6.0, 8.0, 10.0):
    for zl in (0.16, 0.20, 0.24, 0.28):
        p = dict(BASE)
        p['XNEAR'] = xn
        p['ZLOW'] = zl
        show(f'XN={xn} ZL={zl}', score(D, **p))
