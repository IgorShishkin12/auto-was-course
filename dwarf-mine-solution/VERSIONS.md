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
- Status: SHIPPED for user scoring (test score pending)
- Notes: abandons 25-60m range group entirely (S-math: far costs more F than it gains R).
