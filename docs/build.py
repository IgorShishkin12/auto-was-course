#!/usr/bin/env python3
"""Static writeups site generator: markdown + front-matter -> self-contained HTML."""
import os, re, html, markdown, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "site")
CATS = {"web": "Web", "crypto": "Crypto", "reverse": "Reverse", "forensics": "Forensics",
        "android": "Mobile", "misc": "Misc"}

CSS = """
:root{--bg:#0e1116;--panel:#151a22;--panel2:#1b2230;--fg:#e6edf3;--dim:#8b949e;
--acc:#7ee787;--acc2:#58a6ff;--warn:#f0883e;--line:#232b36;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
a{color:var(--acc2);text-decoration:none}a:hover{text-decoration:underline}
header.hero{padding:56px 24px 40px;border-bottom:1px solid var(--line);
background:radial-gradient(900px 300px at 20% -10%,rgba(88,166,255,.18),transparent),
           radial-gradient(700px 260px at 85% 0%,rgba(126,231,135,.13),transparent)}
.wrap{max-width:1080px;margin:0 auto}
h1{margin:0 0 8px;font-size:34px;letter-spacing:-.5px}
.sub{color:var(--dim);font-size:16px;margin:0 0 18px}
.stats{display:flex;gap:10px;flex-wrap:wrap}
.pill{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:4px 12px;font-size:13px;color:var(--dim)}
.pill b{color:var(--fg)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;padding:32px 24px 64px;max-width:1080px;margin:0 auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px;
transition:.15s border-color,.15s transform}
.card:hover{border-color:#2f81f7;transform:translateY(-2px)}
.card .cat{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);font-weight:700}
.card h3{margin:8px 0 6px;font-size:18px;line-height:1.3}
.card p{margin:0;color:var(--dim);font-size:14px}
.card .meta{margin-top:12px;font-size:12px;color:#6e7681;font-family:var(--mono)}
article{max-width:900px;margin:0 auto;padding:40px 24px 80px}
article .back{font-size:14px;color:var(--dim)}
article h1{font-size:30px;margin:14px 0 18px}
article h2{font-size:21px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
article h3{font-size:17px;margin:24px 0 8px;color:var(--acc)}
article p,article li{color:#c9d1d9}
code{font-family:var(--mono);font-size:.9em;background:var(--panel2);padding:2px 6px;border-radius:6px;color:#ffa657}
pre{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;overflow:auto}
pre code{background:none;padding:0;color:#d4e0ea;font-size:13.5px}
blockquote{margin:16px 0;padding:10px 16px;border-left:3px solid var(--acc2);background:var(--panel);color:var(--dim);border-radius:0 10px 10px 0}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14.5px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--panel2);color:var(--dim);font-weight:600}
hr{border:none;border-top:1px solid var(--line);margin:28px 0}
footer{border-top:1px solid var(--line);padding:24px;color:#6e7681;font-size:13px;text-align:center}
.tag{display:inline-block;font-size:11px;color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:2px 7px;margin:2px 4px 0 0;font-family:var(--mono)}
"""

def parse(path):
    raw = open(path, encoding="utf-8").read()
    meta = {}
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                v = v.strip().strip('"')
                if v.startswith("["):
                    v = [x.strip() for x in v.strip("[]").split(",") if x.strip()]
                meta[k.strip()] = v
    else:
        body = raw
    return meta, body.strip()

def page(title, body, extra=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}{extra}</body></html>"""

def main():
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    items = []
    for cat in CATS:
        d = os.path.join(ROOT, cat)
        if not os.path.isdir(d): continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"): continue
            meta, body = parse(os.path.join(d, fn))
            slug = fn[:-3]
            html_body = markdown.markdown(body, extensions=["fenced_code", "tables", "sane_lists"])
            title = meta.get("title", slug)
            desc = re.sub(r"[#*`>\-]", "", body.split("\n\n")[1] if "\n\n" in body else body)[:150].strip()
            tags = meta.get("tags", [])
            if isinstance(tags, str): tags = [tags]
            taghtml = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)
            out = page(title, f"""<article><a class="back" href="../index.html">&larr; all writeups</a>
<h1>{html.escape(title)}</h1>
<p>{taghtml}</p>{html_body}</article>
<footer>YDS CTF — writeups. Flags omitted by design.</footer>""")
            os.makedirs(os.path.join(OUT, cat), exist_ok=True)
            open(os.path.join(OUT, cat, slug + ".html"), "w", encoding="utf-8").write(out)
            items.append(dict(cat=cat, catname=CATS[cat], slug=slug, title=title,
                              desc=desc, meta=meta, tags=tags))

    items.sort(key=lambda x: (list(CATS).index(x["cat"]), x["title"]))
    cards = ""
    for it in items:
        host = it["meta"].get("host") or it["meta"].get("artifact") or ""
        cards += f"""<a class="card" href="{it['cat']}/{it['slug']}.html">
<div class="cat">{it['catname']}</div><h3>{html.escape(it['title'])}</h3>
<p>{html.escape(it['desc'][:140])}</p>
<div class="meta">{html.escape(host)}</div></a>"""

    n = len(items)
    ncat = len({i["cat"] for i in items})
    idx = page("YDS CTF — writeups", f"""<header class="hero"><div class="wrap">
<h1>YDS CTF — writeups</h1>
<p class="sub">Solutions for the is-course.ru competition: web, crypto, reverse, forensics and mobile.
Every writeup documents the vulnerability, the exploit and the fix. <b>Flags are intentionally omitted.</b></p>
<div class="stats"><span class="pill"><b>{n}</b> writeups</span>
<span class="pill"><b>{ncat}</b> categories</span>
<span class="pill">self-contained · no trackers</span></div></div></header>
<div class="grid">{cards}</div>
<footer>Built from Markdown sources · no flags inside</footer>""")
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(idx)
    print(f"built {n} pages -> {OUT}")

if __name__ == "__main__":
    main()
