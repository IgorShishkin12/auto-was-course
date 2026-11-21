---
title: "None shall pass — JWT alg:none"
category: Crypto / Web
host: none-shall-pass.is-course.ru
tags: [jwt, alg-none, cve-2025-59685]
---

# None shall pass

## Recon
The app issues a JWT on signup and gates a "Restricted Page" on it. Decoding the token:

```json
{"alg":"HS256","typ":"JWT"}.{"user":"guest","role":"user"}.<sig>
```

The verifier reads the algorithm **from the token header** and dispatches on it.

## Exploit
Set `"alg":"none"`, keep the payload, drop the signature entirely:

```
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4ifQ.
```

The server accepts the unsigned token, `role=admin` unlocks the restricted page, and the flag is
rendered there.

This is the modern incarnation of the `alg:none` family (cf. CVE-2025-59685): the lesson is that the
*verifier* must pin a single algorithm and must reject tokens whose `alg` is `none` or was not
configured — the header is attacker-controlled data, not a trusted instruction.

## Fix
```go
token, err := jwt.ParseWithClaims(raw, &Claims{}, func(t *jwt.Token) (any, error) {
    if t.Method.Alg() != "HS256" { return nil, errors.New("unexpected alg") }
    return secret, nil
})
```
