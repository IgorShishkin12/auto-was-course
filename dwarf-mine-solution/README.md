# Dwarf-mine obstacle detection (agent solution)

LiDAR point-cloud obstacle detector: per-frame track following (rails +
roadbed contrast, RANSAC, ring-median Zb grade) + tight clearance-gate +
clip-level confirmation. Built and tuned with an AI agent (Arena Agent Mode).

## Layout

- `tracklib.py` — geometry core: `track_slices`, `fit_models`,
  `ring_profile_detections`, `ransac_inliers`, `build_polyline`,
  `predict_mask`, `_default_fit` fallback.
- `predict.py` — split runner: NPZ dir -> packed `.bin` bitstream
  (lexicographic order, `bitorder='little'`) + diag file; clip confirmation
  (total>=15 AND near-confirm X<=11 points>=8).
- `evaluate.py` — official metric (S = R·P·(1−F)²).
- `analyze_gate.py` — per-point gate-coordinate collector for offline
  operating-point search.
- `VERSIONS.md` — log of versioned test predictions.
- `predictions_v1.bin` — v1 test predictions (45167074 bits, exact size
  verified). **Val: R=0.330, P=0.914, F=0.0074, S=0.2970.**
- `predictions_val.bin`, `diag_val.txt` — val confirmation of v1 config.
- `gate_val_wide.npz`, `units_val.npz`, `posframes_val.npz` — offline-search
  artifacts (val).
- `viz/` — diagnostic figures.

## Reproduce

Needs `train/`, `val/`, `test/` NPZ dirs next to the scripts
(`points float32[N,3]`, `frame_offsets int64[T+1]`).

```bash
pip install numpy scipy scikit-learn numba matplotlib
python3 predict.py val predictions_val.bin     # -> predictions_val.bin + diag
python3 evaluate.py --data val --predictions predictions_val.bin
python3 predict.py test predictions_v2.bin
```

Dataset (~2 GB zip, train 80 / val 24 / test 1000 files) is NOT in git.
Yandex.Disk links (provided by task owner):

- dataset: https://disk.yandex.ru/d/fipEjm897JxbEw
- metric script: https://disk.yandex.ru/d/Vzl9cC7pq-zlLA
- video: https://disk.yandex.ru/i/gYbIi7AJ601Plw

## Notes

- Main branch is untouched; all work lives on `agent/dwarf-mine-solution`.
- v1 abandons the 25–60 m range group by design (S-math: far range costs
  more F than it gains R). See VERSIONS.md.
