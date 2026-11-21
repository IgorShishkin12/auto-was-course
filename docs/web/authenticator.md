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

## Fix
Do not accept arbitrary `OID` maps from clients; build the subject from server-side data only, and
validate the parsed certificate subject after issuance.
