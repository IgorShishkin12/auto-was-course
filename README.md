# YDS CTF writeups

Solutions for the *is-course.ru* competition (web, crypto, reverse, forensics, mobile), written up
after the fact: what the challenge was, how it was solved, and how to fix it.

**Flags are intentionally omitted** from every page.

## Layout

```
web/ crypto/ reverse/ forensics/ android/ misc/   Markdown sources (one file per writeup)
build.py                                          static site generator
site/                                             generated, self-contained HTML (open index.html)
```

## Build

```bash
pip install markdown pygments
python3 build.py      # writes ./site
```

The output has no external dependencies: CSS, JS, the search index and the syntax highlighting are all
inlined, so `site/index.html` works offline and from `file://`.

## Contents

| Category | Writeups |
|---|---|
| Web | Authenticator (CSR CN smuggling), cats (admin-bot post-mortem), Clicker (pickle RCE), Moodquery (HMAC key confusion), Network check (command injection), Pillar (XOR cookie), XXE (OOB), gorilla/securecookie reference |
| Crypto | AES-ECB byte-at-a-time, SHA-256 length extension, JWT algorithm confusion, JWT `alg:none`, RSA common modulus |
| Reverse | Local types (wire protocol), Preload (OLLVM vs linear algebra), simple |
| Forensics | Mario (pcap + TLS keylog via LFI) |
| Mobile | Android WebView series (5 tasks) |
| Misc | gdb antics, SuperPrivate, methodology |
