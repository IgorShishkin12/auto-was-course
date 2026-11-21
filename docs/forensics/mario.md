---
title: "Mario — pcap + TLS keylog via LFI"
category: Forensics
host: mario.is-course.ru
tags: [pcap, tls-1.2, lfi, sslkeylog, aes-gcm]
---

# Mario

## Two halves
The handout is `mario.pcap`: one real Chrome TLS 1.2 session (ECDHE-X25519, AES-256-GCM-SHA384, EMS)
to `mario.is-course.ru`. Nothing in cleartext, no covert channels in the headers — it cannot be
decrypted from the file alone. The flag hint says *"decrypt pcap"*, so the key material must come from
the live app.

## Getting the key material
`mario.is-course.ru/change-theme` renders `static/styles/<theme>` into a `<style>` block, with the
`theme` cookie only "whitelisted" by prefix — a classic **path traversal LFI**:

```
theme = ../../etc/nginx/nginx.conf
```

`nginx.conf` contains
```
log_format sslkeylog '$keylog_lines';
access_log /var/log/nginx/sslkeys.log;
```
and that log holds `CLIENT_RANDOM <client_random> <master_secret>` for every connection, including the
one in the pcap (`client_random c6b4081b0dd339fe...` → master `4fabc55b...5b3f0b`).

## Decrypting
`decrypt.py` implements the TLS 1.2 PRF (SHA-384) and AES-256-GCM record decryption, rebuilding the
per-record nonce from the explicit nonce and the sequence number, and the AAD per RFC 5246.

Plaintext of the interesting response:
```
GET /flag?action=107b44da8a3cb3b4973bf6e245b7440299680869
YDS{…redacted…}
```

## Files
`mario/{lfi.py, grab.py, decrypt.py, sslkeys.log, decrypted.txt, mario_access.log}`

## Takeaway
Forensics challenges are often a *chain*: the pcap is the payload, the web app is the key escrow. Always
look for `sslkeylogfile`/`SSLKEYLOGFILE` style artefacts server-side when a capture looks perfect.
