"""Stage-2 offline grid: joint XCAP + near-low + far-tier + confirm."""
import sys, itertools
sys.path.insert(0, '/home/user')
from offline_search import load, score, show

D = load()
BASE = dict(LAT=0.55, ZBOT=0.36, ZTOP=1.15, XCAP=12.0, CMIN=15, CX=11.0, CN=8)
res = []


def run(name, **kw):
    p = dict(BASE)
    p.update(kw)
    d = score(D, **p)
    res.append((d['S'], name, d))
    show(name, d)


print('--- XCAP x near-low ---')
for xc, (xn, zl) in itertools.product(
        (12.5, 13.0, 13.5, 14.0),
        ((6, 0.20), (8, 0.20), (8, 0.18), (6, 0.18), (8, 0.22), (4, 0.16))):
    run(f'XC={xc} XN={xn} ZL={zl}', XCAP=xc, XNEAR=xn, ZLOW=zl)

print('--- far tier (base XCAP=12) ---')
for xf1, latf, zbf in itertools.product(
        (15.0, 18.0, 22.0), (0.30, 0.40, 0.55), (0.36, 0.50)):
    run(f'XF1={xf1} LATF={latf} ZBF={zbf}', XF1=xf1, LATF=latf, ZBF=zbf)

print('--- far tier on XC13+NL62 ---')
for xf1, latf, zbf in itertools.product(
        (15.0, 18.0), (0.30, 0.40), (0.36, 0.50)):
    run(f'XC13NL XF1={xf1} LATF={latf} ZBF={zbf}',
        XCAP=13.0, XNEAR=6.0, ZLOW=0.20, XF1=xf1, LATF=latf, ZBF=zbf)

print('--- confirm variants on XC13+NL62 ---')
for cmin, cx, cn in itertools.product((12, 15, 18), (11.0, 12.0), (6, 8, 10)):
    run(f'CM={cmin} CX={cx} CN={cn}', XCAP=13.0, XNEAR=6.0, ZLOW=0.20,
        CMIN=cmin, CX=cx, CN=cn)

res.sort(reverse=True)
print('=== TOP 10 ===')
for s, name, d in res[:10]:
    show(f'{s:.5f} {name}', d)
