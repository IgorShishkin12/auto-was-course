"""Build units + posframes tables for a labeled split (offline metric)."""
import sys, os, glob
import numpy as np
from collections import defaultdict


def main(dataroot, prefix):
    files = sorted(glob.glob(os.path.join(dataroot, '*.npz')))
    pos = []
    units = defaultdict(int)
    for fi, f in enumerate(files):
        d = np.load(f)
        pts = d['points']
        off = d['frame_offsets']
        lab = d['labels']
        ids = d['object_ids']
        T = len(off) - 1
        dist = np.linalg.norm(pts, axis=1)
        for k in range(T):
            s, e = off[k], off[k + 1]
            m = lab[s:e] == 1
            if not m.any():
                continue
            pos.append((fi, k))
            for o in np.unique(ids[s:e][m]):
                elg = m & (ids[s:e] == o)
                g = int(np.searchsorted([10., 25.],
                                        np.median(dist[s:e][elg]),
                                        side='right'))
                units[(fi, k // 10, int(o), g)] += 1
    keys = np.array(sorted(units), dtype=np.int32)
    n = np.array([units[t] for t in map(tuple, keys)], dtype=np.int32)
    clips = np.array(sorted({(a, b) for a, b, _, _ in units}), dtype=np.int32)
    pos = np.array(sorted(pos), dtype=np.int32)
    np.savez_compressed(f'{prefix}_units.npz', keys=keys, n=n, clips=clips)
    np.savez_compressed(f'{prefix}_posframes.npz', pos=pos)
    print(f'{dataroot}: units={len(keys)} posframes={len(pos)} '
          f'posclips={len(clips)}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
