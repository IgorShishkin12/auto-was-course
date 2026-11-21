#!/bin/bash
# Ship predictions_v3.bin: predict -> verify -> VERSIONS.md -> GitHub branch.
# Usage: ./ship_v3.sh "k=v k=v ..."   (params forwarded to predict_v3.py)
set -e
cd /home/user
PARAMS="$1"
echo "=== v3 ship: $PARAMS"
python3 predict_v3.py test predictions_v3.bin - - $PARAMS
python3 - << 'PY'
import glob, numpy as np
n = sum(int(np.load(f)['frame_offsets'][-1]) for f in sorted(glob.glob('test/*.npz')))
exp = (n + 7) // 8
import os
got = os.path.getsize('predictions_v3.bin')
raw = open('predictions_v3.bin','rb').read()
ones = int(np.unpackbits(np.frombuffer(raw, np.uint8), bitorder='little')[:n].sum())
pad = bin(raw[-1]).count('1') if n % 8 else 0
print(f'pts={n} expected_bytes={exp} got={got} ones={ones} padbits={pad}')
assert got == exp, 'SIZE MISMATCH'
assert n % 8 == 0 or raw[-1] >> (n % 8) == 0, 'NONZERO PADDING'
import hashlib
print('md5:', hashlib.md5(raw).hexdigest())
PY
echo "=== append VERSIONS.md manually after scoring context ==="
