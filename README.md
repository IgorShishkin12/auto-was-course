# YDS CTF — writeups

Solutions for the is-course.ru ("Безопасность информационных систем") challenges.

**No flags are published here.** Each writeup describes the vulnerability, the exploitation path and
the mitigation; the flag value itself is intentionally redacted.

## Contents

| Category | Writeups |
|---|---|
| Web | command injection (cmd), pickle RCE (unserialize), XXE OOB, cookie XOR (pillar), HMAC key confusion (moodquery), CSR CN smuggling (authenticator) |
| Crypto | AES-ECB byte-at-a-time, RSA common modulus, JWT `alg:none`, RS256→HS256 confusion, SHA-256 length extension |
| Reverse | `simple` (cmp chain), preload (OLLVM + GF(2)), local_types (protocol RE + type confusion) |
| Forensics | mario (pcap + TLS keylog via LFI) |
| Mobile | WebView series (5 tasks), SuperPrivate |

Rendered version: `docs/index.html` (self-contained, no external assets).

## Rebuild

```bash
pip install markdown
python3 docs/build.py     # markdown -> docs/site
```
