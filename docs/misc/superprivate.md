---
title: "SuperPrivate — exported activity, local exploit"
category: Mobile
artifact: app-release.apk (com.yandex.shad.homework)
tags: [android, exported-activity, adb, local-exploit]
---

# SuperPrivate

## Recon
The manifest contains `com.yandex.shad.homework.features.SuperPrivateActivity` — "super private". Two
red flags at once: the activity is **exported**, and `classes.dex` shows
`getFlagSuperPrivate` exposed through the same JavaScript bridge as the rest of the series.

## Exploit
There is no server side and no filter: the flag is reachable from the device itself (`adb`, or any
installed app), which is exactly what "local exploit" in the flag text alludes to.

```bash
adb shell am start -n com.yandex.shad.homework/.features.SuperPrivateActivity
# or, with the extra/deep-link parameter the activity expects:
adb shell am start -n com.yandex.shad.homework/.features.SuperPrivateActivity \
  --es <key> <value>
```

The activity decides "private" client-side, so launching it directly renders the protected content.

## Takeaway
`android:exported="true"` is an API contract with every other app on the device. Anything the UI hides
behind navigation must be enforced by the component's own `intent-filter` checks (or by not exporting
it at all), never by client-side state.
