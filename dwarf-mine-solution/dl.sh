#!/bin/bash
# Robust Yandex.Disk re-download with resume + fresh href per attempt.
cd /home/user
EXPECT=2030470008
for attempt in $(seq 1 25); do
  HREF=$(curl -s 'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=https://disk.yandex.ru/d/fipEjm897JxbEw' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['href'])")
  curl -L -C - --retry 3 --retry-delay 5 --speed-limit 100000 --speed-time 90 \
    -o dwarf_mine_dataset.zip "$HREF" >>download.log 2>&1
  SZ=$(stat -c%s dwarf_mine_dataset.zip 2>/dev/null || echo 0)
  echo "attempt $attempt size=$SZ"
  if [ "$SZ" = "$EXPECT" ]; then echo DOWNLOAD_OK; break; fi
  sleep 8
done
