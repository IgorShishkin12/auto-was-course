#!/usr/bin/env python3
"""
Static writeups site generator.

Markdown (+ YAML-ish front matter) -> self-contained HTML.
No external requests: CSS, JS, and the search index are all inlined, and
syntax highlighting uses Pygments classes emitted with a custom dark theme.

Features
  * index page with live search, category filters and tag chips
  * per-article table of contents, reading time, prev/next navigation
  * copy-to-clipboard buttons on every code block
  * print stylesheet
"""
import os, re, html, json, shutil, unicodedata
import markdown
from pygments.formatters import HtmlFormatter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")

# order matters: this is the order of the category nav and of the grid
CATS = [
    ("web", "Web"),
    ("crypto", "Crypto"),
    ("reverse", "Reverse"),
    ("forensics", "Forensics"),
    ("android", "Mobile"),
    ("misc", "Misc"),
    ("tools", "Tooling"),
]
CATNAME = dict(CATS)

SITE_TITLE = "YDS CTF — writeups"
SITE_SUB = ("Solutions for the is-course.ru competition: web, crypto, reverse, forensics and mobile. "
            "Each page documents the vulnerability, the exploit, and how to fix it. "
            "<b>Flags are intentionally omitted.</b>")

# --------------------------------------------------------------------------- css
PALETTE = """
:root{
  --bg:#0b0e13; --bg2:#0f131a; --panel:#141a23; --panel2:#1a2230; --line:#232c3a;
  --fg:#e6edf3; --fg2:#c3cdd8; --dim:#8b949e; --faint:#6e7681;
  --acc:#7ee787; --acc2:#6cb6ff; --acc3:#d2a8ff; --warn:#f0883e; --err:#ff7b72;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.68 var(--sans);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--acc2);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:3px}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}
code,kbd,pre{font-family:var(--mono)}

/* ---------- top bar ---------- */
header.top{position:sticky;top:0;z-index:50;background:rgba(11,14,19,.86);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;align-items:center;gap:18px;height:56px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;letter-spacing:-.2px;color:var(--fg)}
.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--acc);
  box-shadow:0 0 12px rgba(126,231,135,.75)}
.brand small{color:var(--faint);font-weight:500;letter-spacing:0}
nav.top-nav{display:flex;gap:4px;margin-left:auto;flex-wrap:wrap}
nav.top-nav a{font-size:13.5px;color:var(--dim);padding:6px 10px;border-radius:8px}
nav.top-nav a:hover{background:var(--panel);color:var(--fg);text-decoration:none}
nav.top-nav a.on{background:var(--panel2);color:var(--fg)}

/* ---------- hero ---------- */
header.hero{padding:64px 0 40px}
header.hero h1{margin:0 0 10px;font-size:clamp(30px,5vw,44px);letter-spacing:-1.2px}
header.hero .eyebrow{font:600 12px/1 var(--mono);letter-spacing:.22em;text-transform:uppercase;
  color:var(--acc);margin-bottom:16px}
header.hero p.sub{color:var(--dim);font-size:17px;max-width:62ch;margin:0 0 22px}
.stats{display:flex;gap:8px;flex-wrap:wrap}
.pill{border:1px solid var(--line);background:var(--panel);border-radius:999px;
  padding:5px 13px;font-size:13px;color:var(--dim)}
.pill b{color:var(--fg)}

/* ---------- search + filters ---------- */
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 22px}
#q{flex:1 1 280px;min-width:220px;background:var(--panel);border:1px solid var(--line);
  color:var(--fg);border-radius:11px;padding:11px 14px;font:15px var(--sans);outline:none}
#q:focus{border-color:var(--acc2);box-shadow:0 0 0 3px rgba(108,182,255,.14)}
#q::placeholder{color:var(--faint)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:13px;color:var(--dim);background:var(--panel);border:1px solid var(--line);
  border-radius:999px;padding:6px 12px;cursor:pointer;user-select:none}
.chip:hover{color:var(--fg);border-color:#2f3b4c}
.chip.on{background:rgba(108,182,255,.14);border-color:rgba(108,182,255,.5);color:#cfe6ff}
#hits{color:var(--faint);font-size:13px;font-family:var(--mono)}

/* ---------- cards ---------- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(316px,1fr));gap:16px;padding:0 0 72px}
.card{display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);
  border-radius:16px;padding:18px 18px 16px;transition:border-color .15s,transform .15s,background .15s}
.card:hover{border-color:#33507a;background:#161d27;transform:translateY(-2px);text-decoration:none}
.card .cat{font:700 10.5px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--acc)}
.card h3{margin:10px 0 7px;font-size:17.5px;line-height:1.32;color:var(--fg);letter-spacing:-.2px}
.card p{margin:0;color:var(--dim);font-size:14px;line-height:1.55}
.card .meta{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);
  font:12px var(--mono);color:var(--faint);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.card .meta .rt{margin-left:auto;color:#5b6472}
.tag{display:inline-block;font:11px var(--mono);color:var(--dim);border:1px solid var(--line);
  border-radius:6px;padding:3px 7px;background:var(--bg2)}

/* ---------- article ---------- */
article{max-width:860px;margin:0 auto;padding:34px 24px 90px}
.crumbs{font-size:13px;color:var(--faint);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.crumbs a{color:var(--dim)}
article h1{font-size:clamp(26px,4vw,36px);letter-spacing:-.9px;margin:16px 0 12px;line-height:1.2}
article>p.tags{margin:0 0 8px}
.artmeta{display:flex;gap:14px;flex-wrap:wrap;color:var(--faint);font:12.5px var(--mono);
  margin:0 0 26px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.artmeta a{color:var(--dim)}
h2,h3,h4{scroll-margin-top:76px}
article h2{font-size:21px;margin:38px 0 12px;letter-spacing:-.3px}
article h2::before{content:"";display:block;width:34px;height:2px;background:var(--acc);
  margin-bottom:12px;border-radius:2px}
article h3{font-size:17px;margin:26px 0 8px;color:var(--acc2)}
article h4{font-size:15px;margin:20px 0 6px;color:var(--fg2)}
article p,article li{color:var(--fg2)}
article ul,article ol{padding-left:22px}
article li{margin:5px 0}
article li::marker{color:var(--faint)}
blockquote{margin:20px 0;padding:12px 18px;border-left:3px solid var(--acc2);
  background:var(--bg2);color:var(--dim);border-radius:0 10px 10px 0}
blockquote p{margin:6px 0}
blockquote.warn{border-left-color:var(--warn)}
blockquote.ok{border-left-color:var(--acc)}
hr{border:none;border-top:1px solid var(--line);margin:34px 0}

/* ---------- code ---------- */
code{font-size:.885em;background:var(--panel2);padding:2px 6px;border-radius:6px;color:#ffb57e}
pre{position:relative;background:var(--bg2);border:1px solid var(--line);border-radius:12px;
  padding:16px 16px;overflow:auto;margin:18px 0;font-size:13.4px;line-height:1.62}
pre code{background:none;padding:0;color:#d7e2ec;font-size:inherit}
.copy{position:absolute;top:9px;right:9px;font:11px var(--mono);color:var(--dim);
  background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:4px 8px;
  cursor:pointer;opacity:0;transition:opacity .15s,color .15s}
pre:hover .copy{opacity:1}
.copy:hover{color:var(--fg);border-color:#3a4759}

/* ---------- tables ---------- */
table{border-collapse:collapse;width:100%;margin:18px 0;font-size:14.2px;display:block;overflow:auto}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
th{background:var(--panel2);color:var(--fg2);font-weight:600;white-space:nowrap}
tr:nth-child(even) td{background:rgba(255,255,255,.014)}

/* ---------- toc ---------- */
.toc{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:16px 18px;margin:0 0 30px}
.toc .t{font:700 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--faint);margin-bottom:10px}
.toc ol{margin:0;padding-left:18px;color:var(--dim);font-size:14px}
.toc li{margin:4px 0}
.toc a{color:var(--dim)}
.toc a:hover{color:var(--acc2)}

/* ---------- prev / next ---------- */
.pager{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:44px 0 0;
  padding-top:24px;border-top:1px solid var(--line)}
.pager a{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:12px 14px;display:block}
.pager a:hover{border-color:#33507a;text-decoration:none}
.pager .lbl{font:11px var(--mono);color:var(--faint);letter-spacing:.1em;text-transform:uppercase}
.pager .ttl{color:var(--fg);font-size:14.5px;margin-top:3px}
.pager .next{text-align:right}

footer{border-top:1px solid var(--line);padding:26px 24px 40px;color:var(--faint);
  font-size:12.5px;text-align:center}
footer a{color:var(--dim)}
.empty{color:var(--faint);padding:40px 0;text-align:center;font-size:15px}

/* ---------- matrix ---------- */
section.matrix{margin:0 0 34px}
section.matrix h2{font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);
  font-family:var(--mono);margin:0 0 12px;font-weight:700}
section.matrix table{display:table;font-size:14px}
section.matrix td:first-child{white-space:nowrap;color:var(--faint);font-family:var(--mono);font-size:12px}
section.matrix td.tech{color:var(--dim)}
.badge{display:inline-block;font:11px var(--mono);border-radius:999px;padding:2px 9px;white-space:nowrap}
.badge.solved{color:#7ee787;background:rgba(126,231,135,.12);border:1px solid rgba(126,231,135,.35)}
.badge.open{color:#f0883e;background:rgba(240,136,62,.12);border:1px solid rgba(240,136,62,.35)}
.badge.reference{color:#6cb6ff;background:rgba(108,182,255,.12);border:1px solid rgba(108,182,255,.35)}

@media (max-width:640px){
  .pager{grid-template-columns:1fr}
  nav.top-nav{display:none}
  article{padding-top:24px}
}
@media print{
  header.top,footer,.toolbar,.pager,.copy{display:none!important}
  body{background:#fff;color:#111}
  article{max-width:none;padding:0}
  a{color:#0645ad}
  pre,table,bq{border-color:#ccc}
  article p,article li{color:#222}
}
"""

PYG = HtmlFormatter(style="github-dark").get_style_defs(".codehilite")
CSS = PALETTE + "\n.codehilite{background:transparent}\n" + PYG + """
pre .codehilite, .codehilite pre{background:transparent;border:0;padding:0;margin:0}
"""

# --------------------------------------------------------------------------- helpers
def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", text) or "section"


def parse_front_matter(raw):
    meta = {}
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            meta[k.strip()] = v
    else:
        body = raw
    return meta, body.strip()


def plain(text, limit=None):
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"[#*_`>|\-]+", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit] if limit else t


def render(md_text):
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "codehilite", "tables", "sane_lists",
                    "attr_list", "toc", "def_list", "footnotes"],
        extension_configs={"codehilite": {"guess_lang": False, "noclasses": False,
                                          "css_class": "codehilite"}},
    )


def add_anchors_and_toc(body_html):
    """Give every h2 an id and build a TOC from them."""
    headings = []

    def repl(m):
        level, attrs, text = m.group(1), m.group(2), m.group(3)
        if level != "2":
            return m.group(0)
        plain_text = re.sub(r"<[^>]+>", "", text)
        sid = slugify(plain_text)
        n = 2
        base = sid
        while any(h[1] == sid for h in headings):
            sid = f"{base}-{n}"
            n += 1
        headings.append((plain_text, sid))
        return f'<h2 id="{sid}"{attrs}>{text}</h2>'

    body_html = re.sub(r"<h([1-4])([^>]*)>(.*?)</h\1>", repl, body_html, flags=re.S)
    if len(headings) < 2:
        return body_html, ""
    items = ""


def build_toc(headings):
    if len(headings) < 2:
        return ""
    li = "\n".join(f'<li><a href="#{sid}">{html.escape(t)}</a></li>' for t, sid in headings)
    return f'<nav class="toc"><div class="t">On this page</div><ol>{li}</ol></nav>'


def page(title, body, extra_head="", body_class=""):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f"<style>{CSS}</style>{extra_head}</head>"
        f'<body class="{body_class}">{body}</body></html>'
    )


def topbar(active=None, rel=""):
    links = []
    for key, name in CATS:
        cls = " class=\"on\"" if key == active else ""
        links.append(f'<a href="{rel}index.html#{key}"{cls}>{name}</a>')
    return (
        '<header class="top"><div class="wrap">'
        f'<a class="brand" href="{rel}index.html"><span class="dot"></span>YDS CTF '
        '<small>writeups</small></a>'
        f'<nav class="top-nav">{"".join(links)}<a href="{rel}index.html">All</a></nav>'
        "</div></header>"
    )


COPY_JS = """
<script>
document.querySelectorAll('pre').forEach(function(pre){
  var b=document.createElement('button');
  b.className='copy'; b.textContent='copy';
  b.addEventListener('click',function(){
    var t=pre.querySelector('code'); t=t?t.innerText:pre.innerText;
    navigator.clipboard.writeText(t).then(function(){
      b.textContent='copied'; setTimeout(function(){b.textContent='copy';},1200);
    });
  });
  pre.appendChild(b);
});
</script>
"""

# --------------------------------------------------------------------------- build
def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    items = []
    for cat, catname in CATS:
        d = os.path.join(ROOT, cat)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            meta, body = parse_front_matter(open(os.path.join(d, fn), encoding="utf-8").read())
            items.append(dict(cat=cat, catname=catname, slug=fn[:-3], meta=meta, body=body,
                              title=meta.get("title", fn[:-3])))

    order = {k: i for i, (k, _) in enumerate(CATS)}
    items.sort(key=lambda x: (order[x["cat"]], x["title"].lower()))

    # ---------------- article pages
    for i, it in enumerate(items):
        body_html = render(it["body"])

        # ids + toc
        headings = []
        def repl(m):
            level, attrs, text = m.group(1), m.group(2), m.group(3)
            plain_t = re.sub(r"<[^>]+>", "", text)
            sid = slugify(plain_t)
            n, base = 2, sid
            while any(h[1] == sid for h in headings):
                sid = f"{base}-{n}"; n += 1
            headings.append((plain_t, sid))
            return f'<h{level} id="{sid}"{attrs}>{text}</h{level}>'
        body_html = re.sub(r"<h([2-4])([^>]*)>(.*?)</h\1>", repl, body_html, flags=re.S)
        toc = build_toc(headings)

        words = len(plain(it["body"]).split())
        rt = max(1, round(words / 200))
        tags = it["meta"].get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        taghtml = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)
        host = it["meta"].get("host") or it["meta"].get("artifact") or ""

        prev_it = items[i - 1] if i > 0 else None
        next_it = items[i + 1] if i + 1 < len(items) else None
        pager = ""
        if prev_it or next_it:
            parts = []
            if prev_it:
                parts.append(f'<a href="{prev_it["slug"]}.html"><div class="lbl">&larr; previous</div>'
                             f'<div class="ttl">{html.escape(prev_it["title"])}</div></a>')
            else:
                parts.append("<span></span>")
            if next_it:
                parts.append(f'<a class="next" href="{next_it["slug"]}.html"><div class="lbl">next &rarr;</div>'
                             f'<div class="ttl">{html.escape(next_it["title"])}</div></a>')
            pager = f'<nav class="pager">{"".join(parts)}</nav>'

        art = (
            topbar(it["cat"], "../")
            + '<article>'
            + f'<div class="crumbs"><a href="../index.html">writeups</a> <span>/</span> '
              f'<a href="../index.html#{it["cat"]}">{it["catname"]}</a></div>'
            + f'<h1>{html.escape(it["title"])}</h1>'
            + f'<p class="tags">{taghtml}</p>'
            + f'<div class="artmeta"><span>{html.escape(host)}</span><span>{rt} min read</span>'
              f'<span>{words} words</span></div>'
            + toc + body_html + pager
            + "</article>"
            + '<footer>YDS CTF writeups &middot; built from Markdown &middot; flags omitted by design</footer>'
            + COPY_JS
        )
        os.makedirs(os.path.join(OUT, it["cat"]), exist_ok=True)
        open(os.path.join(OUT, it["cat"], it["slug"] + ".html"), "w", encoding="utf-8").write(
            page(it["title"] + " — " + SITE_TITLE, art))

        it["rt"] = rt
        it["desc"] = plain(it["body"], 220)
        it["host"] = host
        it["tags"] = tags
        it["words"] = words

    # ---------------- index page
    cards = []
    for it in items:
        tagchips = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in it["tags"][:3])
        cards.append(
            f'<a class="card" data-cat="{it["cat"]}" href="{it["cat"]}/{it["slug"]}.html">'
            f'<div class="cat">{it["catname"]}</div>'
            f'<h3>{html.escape(it["title"])}</h3>'
            f'<p>{html.escape(it["desc"][:150])}&hellip;</p>'
            f'<div class="meta">{tagchips}<span class="rt">{it["rt"]} min</span></div></a>')

    chips = ['<span class="chip on" data-cat="all">All</span>']
    for key, name in CATS:
        n = sum(1 for i in items if i["cat"] == key)
        if n:
            chips.append(f'<span class="chip" data-cat="{key}">{name} <b>{n}</b></span>')

    search_index = [dict(t=i["title"], c=i["catname"], u=f'{i["cat"]}/{i["slug"]}.html',
                         d=i["desc"][:400], g=" ".join(i["tags"])) for i in items]

    n = len(items)
    ncat = len({i["cat"] for i in items})
    total_words = sum(i["words"] for i in items)

    rows = []
    for it in items:
        status = it["meta"].get("status", "solved")
        badge = f'<span class="badge {html.escape(status)}">{html.escape(status)}</span>'
        rows.append(
            "<tr>"
            f'<td>{html.escape(it["catname"])}</td>'
            f'<td><a href="{it["cat"]}/{it["slug"]}.html">{html.escape(it["title"])}</a></td>'
            f'<td class="tech">{re.sub(r"`([^`]+)`", r"<code>\\1</code>", html.escape(it["meta"].get("technique", "")))}</td>'
            f'<td>{badge}</td>'
            "</tr>")
    matrix = (
        '<section class="matrix"><h2>All writeups at a glance</h2>'
        "<table><thead><tr><th>Category</th><th>Task</th><th>Core technique</th>"
        f"<th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>")

    index_body = (
        topbar(None, "")
        + '<header class="hero"><div class="wrap">'
        + '<div class="eyebrow">is-course.ru &middot; capture the flag</div>'
        + f'<h1>{SITE_TITLE}</h1>'
        + f'<p class="sub">{SITE_SUB}</p>'
        + '<div class="stats">'
        + f'<span class="pill"><b>{n}</b> writeups</span>'
        + f'<span class="pill"><b>{ncat}</b> categories</span>'
        + f'<span class="pill"><b>{total_words:,}</b> words</span>'
        + '<span class="pill">self-contained &middot; no trackers</span>'
        + '</div></div></header>'
        + '<div class="wrap">'
        + matrix
        + '<div class="toolbar"><input id="q" type="search" placeholder="Search writeups, tags, hosts&hellip; (press /)" '
          'autocomplete="off" spellcheck="false"><div class="chips">' + "".join(chips) + "</div>"
          '<span id="hits"></span></div>'
        + f'<div class="grid">{"".join(cards)}</div>'
        + '<div class="empty" id="empty" style="display:none">No writeup matches that query.</div>'
        + "</div>"
        + '<footer>Built from Markdown sources &middot; no flags anywhere in this site</footer>'
    )

    index_js = """
<script>
var IDX = %s;
var cards=[].slice.call(document.querySelectorAll('.card'));
var q=document.getElementById('q'), hits=document.getElementById('hits'),
    empty=document.getElementById('empty'), chips=[].slice.call(document.querySelectorAll('.chip'));
var cat='all';
function norm(s){return (s||'').toLowerCase();}
function apply(){
  var term=norm(q.value).trim(), shown=0;
  cards.forEach(function(card,i){
    var rec=IDX[i], okCat=(cat==='all'||card.dataset.cat===cat);
    var okTxt=!term||norm(rec.t+' '+rec.d+' '+rec.g+' '+rec.c).indexOf(term)>=0;
    var vis=okCat&&okTxt;
    card.style.display=vis?'':'none';
    if(vis) shown++;
  });
  hits.textContent=term||cat!=='all'?(shown+' / '+cards.length):'';
  empty.style.display=shown?'none':'block';
}
q.addEventListener('input',apply);
chips.forEach(function(ch){ch.addEventListener('click',function(){
  chips.forEach(function(c){c.classList.remove('on');});
  ch.classList.add('on'); cat=ch.dataset.cat; apply();
});});
document.addEventListener('keydown',function(e){
  if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();}
  if(e.key==='Escape'&&document.activeElement===q){q.value='';apply();q.blur();}
});
if(location.hash&&location.hash.length>1){
  var h=location.hash.slice(1);
  var chip=chips.filter(function(c){return c.dataset.cat===h;})[0];
  if(chip) chip.click();
}
</script>
""" % json.dumps(search_index, ensure_ascii=False)

    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(
        page(SITE_TITLE, index_body + index_js))

    print(f"built {n} writeups across {ncat} categories -> {OUT}")
    for it in items:
        print(f"  {it['cat']:9s} {it['rt']:>2} min  {it['title']}")


if __name__ == "__main__":
    main()
