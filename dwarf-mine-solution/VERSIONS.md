# Versioned test predictions

Each `predictions_v<N>.bin` is a full test-split prediction bitstream
(lexicographic file order, `bitorder='little'`), ready for scoring.
Val numbers are from `evaluate.py --data val` unless noted.

## v1 — tight near gate + clip-min + near-confirm (baseline)
- File: `predictions_v1.bin`
- Gate: |lat|<=0.55, zrel in [0.36, 1.15], X<=12
- Clip logic: keep clip iff total>=15 AND points-with-X<=11 >= 8
- Geometry: ring tracking + rail pairs + RANSAC + ring-median Zb + ring-profile far Yc
- Val: R=0.330 [0.79/0.20/0.00], P=0.914, F=0.0074, S=0.2970 (re-verified 2026-11-20 after data restore)
- Test: 45167074 bits / 5645885 bytes, 14163 ones (0.031%), runtime 1909 s, verified exact size 2026-11-20
- Status: SCORED 0 points (test S<0.30). md5 a42683a1708f3acff7851f280629a08c
- NOTE: v1 ran WITHOUT the _default_fit occlusion fallback (added after the test run started).

## v2 — v1 + occlusion fallback + XCAP13 + near-low band + far tier
- File: `predictions_v2.bin`
- Gate: base |lat|<=0.55, zrel in [0.36, 1.15], X<=13; near-low band X<=7,
  zrel>=0.18 (same lat/top); far tier X in (13,15], |lat|<=0.35,
  zrel in [0.55, 1.15]
- Clip logic: unchanged (total>=15 AND X<=11 points>=8)
- Geometry: + _default_fit fallback (straight centerline + min-of-windows
  strip level) on tracking failure; fixes 29/29 NOFIT frames (all positive,
  pure-TP recovery, 0 FP)
- Val: R=0.3963 [0.925/0.264/0.000], P=0.9256, F=0.0074, S=0.36144
  (full predict.py+evaluate.py run; matches offline_search.py exactly)
- Offline path: 0.33125 (v1 point + fallback) -> 0.35420 (+XCAP13+NL) ->
  0.36144 (+far tier). Far tier with loose bounds rejected by grid.
- Test: 45167074 bits / 5645885 bytes, 21138 ones (0.047%), runtime 1180 s,
  verified exact size 2026-11-20. md5 ed1487e846cb035d547c2a4712bb9fd0
- Status: SHIPPED for user scoring (test score pending)

## Grading buckets (S -> points)
S<0.30:0; 0.30-0.33:1; 0.33-0.37:2; 0.37-0.40:3; 0.40-0.43:4; 0.43-0.47:5;
0.47-0.50:6; 0.50-0.53:7; 0.53-0.56:8; 0.56-0.59:9; 0.59-0.62:10;
0.62-0.65:11; >=0.65:12. Target: cross 0.30 WITH margin (aim val ~0.33+).
- Notes: abandons 25-60m range group entirely (S-math: far costs more F than it gains R).
