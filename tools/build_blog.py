#!/usr/bin/env python3
"""Build the blog from Markdown posts and wire it into the static site.

    python3 tools/build_blog.py

Reads posts/*.md, writes blog/index.html and blog/<slug>/index.html,
adds a Blog link to the nav and footer of every other HTML page, and
inserts the blog URLs into sitemap.xml. GitHub Pages serves the
committed HTML. There is no separate site build.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://homeschoolaitutor.com"
ORG = "The 12-Week AI-Tutor Guides"
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
SUBJECTS = [
    ("subjects/math.html", "Math"),
    ("subjects/science.html", "Science"),
    ("subjects/reading-and-writing.html", "Reading and writing"),
    ("subjects/coding-and-media.html", "Coding and media"),
    ("subjects/arts-and-making.html", "Arts and making"),
    ("subjects/people-and-life.html", "People and life"),
    ("subjects/history-and-the-world.html", "History and the world"),
    ("subjects/work-and-career.html", "Work and career"),
    ("subjects/home-and-hands.html", "Home and hands"),
    ("subjects/food-and-drink.html", "Food and drink"),
    ("subjects/mind-and-body.html", "Mind and body"),
    ("subjects/music-and-art.html", "Music and art"),
    ("subjects/ideas-and-science.html", "Ideas and science"),
    ("subjects/college-admissions.html", "College admissions"),
    ("subjects/ap-exams.html", "AP exams"),
    ("subjects/graduate-school.html", "Graduate school"),
    ("subjects/english-exams.html", "English exams"),
    ("subjects/diplomas-credit-and-life.html", "Diplomas, credit and life"),
]
REQUIRED = ("title", "description", "date", "slug", "summary")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
NAV_RE = re.compile(r'(<a href="[^"]*learn/index\.html">Learn</a>)')
FOOT_RE = re.compile(
    r'(<a href="https://homeschoolaitutor\.etsy\.com">Visit the Etsy shop</a></p>)'
)


def rel_to(page: Path, target: Path) -> str:
    return Path(os.path.relpath(target, start=page.parent)).as_posix()


def format_date(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{MONTHS[month - 1]} {day}, {year}"


def word_count(markdown: str) -> int:
    """Count prose words, ignoring markup, raw tags, and table rules."""
    kept = []
    for line in markdown.splitlines():
        if SEP_RE.match(line):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split()) if text else 0


def inline(src: str) -> str:
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        if src.startswith("**", i):
            j = src.find("**", i + 2)
            if j != -1:
                out.append("<strong>" + inline(src[i + 2 : j]) + "</strong>")
                i = j + 2
                continue
        if src.startswith("[", i):
            match = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", src[i:])
            if match:
                href = html.escape(match.group(2), quote=True)
                out.append(f'<a href="{href}">{inline(match.group(1))}</a>')
                i += match.end()
                continue
        if src.startswith("*", i) and not src.startswith("**", i):
            j = src.find("*", i + 1)
            if j != -1:
                out.append("<em>" + inline(src[i + 1 : j]) + "</em>")
                i = j + 1
                continue
        nxt = n
        for k in range(i + 1, n):
            if src[k] in "*[":
                nxt = k
                break
        out.append(html.escape(src[i:nxt], quote=False))
        i = nxt
    return "".join(out)


def is_block_start(line: str) -> bool:
    stripped = line.lstrip()
    return (
        stripped.startswith("#")
        or stripped.startswith("- ")
        or stripped.startswith("|")
        or stripped.startswith("<div")
        or stripped.startswith("<section")
        or stripped.startswith("<p")
        or bool(re.match(r"\d+\. ", stripped))
    )


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def render_table(rows: list[str]) -> str:
    parsed = [split_row(row) for row in rows]
    header = None
    body = parsed
    if len(rows) >= 2 and SEP_RE.match(rows[1]):
        header = parsed[0]
        body = parsed[2:]
    parts = ["<div class=\"table-wrap\"><table>"]
    if header:
        cells = "".join(f"<th>{inline(cell)}</th>" for cell in header)
        parts.append(f"<thead><tr>{cells}</tr></thead>")
    parts.append("<tbody>")
    for row in body:
        cells = "".join(f"<td>{inline(cell)}</td>" for cell in row)
        parts.append(f"<tr>{cells}</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_markdown(src: str) -> str:
    lines = src.replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith(("<div", "<section", "<p")):
            chunk = [line]
            i += 1
            while i < len(lines) and lines[i].strip():
                chunk.append(lines[i])
                i += 1
            blocks.append("\n".join(chunk))
            continue
        if line.startswith("### "):
            blocks.append(f"<h3>{inline(line[4:].strip())}</h3>")
            i += 1
            continue
        if line.startswith("## "):
            blocks.append(f"<h2>{inline(line[3:].strip())}</h2>")
            i += 1
            continue
        if line.startswith("# "):
            blocks.append(f"<h1>{inline(line[2:].strip())}</h1>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            blocks.append(render_table(rows))
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            blocks.append(f"<ul>\n{lis}\n</ul>")
            continue
        if re.match(r"\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                items.append(re.sub(r"^\d+\. ", "", lines[i]).strip())
                i += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            blocks.append(f"<ol>\n{lis}\n</ol>")
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not is_block_start(lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(blocks)


def parse_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing front matter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path.name}: unterminated front matter")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path.name}: bad front matter line: {line}")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    missing = [key for key in REQUIRED if not meta.get(key)]
    if missing:
        raise ValueError(f"{path.name}: missing {', '.join(missing)}")
    try:
        date.fromisoformat(meta["date"])
    except ValueError as exc:
        raise ValueError(f"{path.name}: date must be YYYY-MM-DD") from exc
    if not SLUG_RE.match(meta["slug"]):
        raise ValueError(f"{path.name}: slug must be lowercase words and hyphens")
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    meta["body"] = body
    meta["source"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
    meta["draft"] = meta.get("draft", "").lower() in {"true", "yes", "1"}
    return meta


def load_posts(directory: Path | None = None) -> list[dict]:
    folder = directory or (ROOT / "posts")
    posts = []
    if not folder.exists():
        return posts
    for path in sorted(folder.glob("*.md")):
        post = parse_post(path)
        if post["draft"]:
            continue
        posts.append(post)
    slugs = [post["slug"] for post in posts]
    dupes = {slug for slug in slugs if slugs.count(slug) > 1}
    if dupes:
        raise ValueError("duplicate slugs: " + ", ".join(sorted(dupes)))
    posts.sort(key=lambda post: (post["date"], post["slug"]), reverse=True)
    return posts


def json_ld(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c")


def article_ld(post: dict, canonical: str) -> str:
    return json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": post["title"],
                    "description": post["description"],
                    "datePublished": post["date"],
                    "dateModified": post.get("updated") or post["date"],
                    "author": {"@type": "Organization", "name": ORG, "url": SITE + "/"},
                    "publisher": {
                        "@type": "Organization",
                        "name": ORG,
                        "url": SITE + "/",
                        "logo": {
                            "@type": "ImageObject",
                            "url": SITE + "/og.png",
                        },
                    },
                    "image": SITE + "/og.png",
                    "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
                    "url": canonical,
                    "inLanguage": "en",
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": 1,
                            "name": "Home",
                            "item": SITE + "/",
                        },
                        {
                            "@type": "ListItem",
                            "position": 2,
                            "name": "Blog",
                            "item": SITE + "/blog/",
                        },
                        {
                            "@type": "ListItem",
                            "position": 3,
                            "name": post["title"],
                            "item": canonical,
                        },
                    ],
                },
            ],
        }
    )


def index_ld(posts: list[dict]) -> str:
    items = []
    for position, post in enumerate(posts, start=1):
        items.append(
            {
                "@type": "ListItem",
                "position": position,
                "url": f"{SITE}/blog/{post['slug']}/",
                "name": post["title"],
            }
        )
    return json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": "Blog",
                    "description": INDEX_DESCRIPTION,
                    "url": SITE + "/blog/",
                    "isPartOf": {
                        "@type": "WebSite",
                        "name": "HomeschoolAITutor",
                        "url": SITE + "/",
                    },
                    "publisher": {"@type": "Organization", "name": ORG, "url": SITE + "/"},
                    "mainEntity": {"@type": "ItemList", "itemListElement": items},
                }
            ],
        }
    )


INDEX_TITLE = "Blog: articles from Homeschool AI Tutor"
INDEX_DESCRIPTION = (
    "Articles for homeschool families, including a 12-week study plan "
    "for the digital PSAT/NMSQT and a homeschool sewing curriculum."
)
INDEX_LEDE = (
    "Practical notes for homeschool families. New pieces show up here "
    "as articles, including a 12-week plan for the digital PSAT and a "
    "guide to teaching sewing at home."
)


def chrome(page: Path, title: str, description: str, canonical: str, ld: str, main: str, og_type: str, extra_meta: str = "") -> str:
    css = rel_to(page, ROOT / "assets" / "site.css")
    js = rel_to(page, ROOT / "assets" / "site.js")
    font = rel_to(page, ROOT / "fonts" / "BricolageGrotesque-normal-500-800.woff2")
    home = rel_to(page, ROOT / "index.html")
    blog_href = rel_to(page, ROOT / "blog" / "index.html")
    current = " aria-current=\"page\"" if "blog" in page.relative_to(ROOT).parts else ""
    subjects = " &middot; ".join(
        f"<a href=\"{html.escape(rel_to(page, ROOT / href), quote=True)}\">{html.escape(label)}</a>"
        for href, label in SUBJECTS
    )
    esc_title = html.escape(title, quote=True)
    esc_desc = html.escape(description, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc_title}</title>
<meta name="description" content="{esc_desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc_title}">
<meta property="og:description" content="{esc_desc}">
<meta property="og:site_name" content="HomeschoolAITutor">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc_title}">
<meta name="twitter:description" content="{esc_desc}">
<meta name="twitter:image" content="{SITE}/og.png">
{extra_meta}<script type="application/ld+json">{ld}</script>
<meta name="p:domain_verify" content="b7b54350f8a1e7ab78636dd2a79082ac">
<link rel="preload" href="{font}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{css}">
</head>
<body>
<!-- Built by tools/build_blog.py from posts/. Edit the Markdown, then rebuild. -->
<header class="top"><div class="wrap">
<a class="mark" href="{home}">Homeschool<span>AI</span>Tutor</a>
<nav class="nav" aria-label="Main"><a href="{home}#shop">Guides</a>
<a href="{rel_to(page, ROOT / "placement-checks.html")}">Free placement checks</a>
<a href="{rel_to(page, ROOT / "learn" / "index.html")}">Learn</a>
<a href="{blog_href}"{current}>Blog</a>
<a href="{rel_to(page, ROOT / "start-here.html")}">Never used AI? Start here</a></nav></div></header>
<main>
{main}
</main>
<footer class="foot"><div class="wrap">
<div><h3>Sold only on Etsy</h3>
<p>Every guide is an instant download from our Etsy shop, HomeschoolAITutor. The guides are
written with AI help, and you run them with an AI tutor of your choice.</p>
<p><a href="https://homeschoolaitutor.etsy.com">Visit the Etsy shop</a></p>
<p><a href="{blog_href}">Blog</a></p></div>
<div><form class="subscribe" action="https://app.kit.com/forms/9983977/subscriptions" method="POST"><h3>Stay in the loop</h3><p>New guides and updates by email. Unsubscribe any time.</p><label class="sr" for="em">Email</label><input id="em" type="email" name="email_address" placeholder="you@example.com" required><button type="submit">Sign me up</button></form></div>
<p class="subjects-all">Browse by subject: {subjects}</p>
</div></footer>
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "7422966addd54beead21aba5c8c03657"}}'></script>
<script src="{js}" defer></script>
</body>
</html>
"""


def render_index(posts: list[dict]) -> str:
    page = ROOT / "blog" / "index.html"
    if posts:
        items = []
        for post in posts:
            items.append(
                "<li>"
                f"<time datetime=\"{post['date']}\">{format_date(post['date'])}</time>"
                f"<h3><a href=\"{post['slug']}/\">{html.escape(post['title'])}</a></h3>"
                f"<p>{html.escape(post['summary'])}</p>"
                "</li>"
            )
        listing = "<ul class=\"learn-list\">\n" + "\n".join(items) + "\n</ul>"
    else:
        listing = "<p>No posts yet.</p>"
    main = f"""<div class="wrap"><article class="article">
<h1>Blog</h1>
<p class="lede">{html.escape(INDEX_LEDE)}</p>
{listing}
</article></div>"""
    return chrome(
        page,
        INDEX_TITLE,
        INDEX_DESCRIPTION,
        SITE + "/blog/",
        index_ld(posts),
        main,
        "website",
    )


def render_post(post: dict) -> str:
    page = ROOT / "blog" / post["slug"] / "index.html"
    canonical = f"{SITE}/blog/{post['slug']}/"
    modified = post.get("updated") or post["date"]
    extra = (
        f'<meta property="article:published_time" content="{post["date"]}">\n'
        f'<meta property="article:modified_time" content="{modified}">\n'
    )
    main = f"""<div class="wrap"><article class="article">
<p class="crumbs"><a href="{rel_to(page, ROOT / "blog" / "index.html")}">Blog</a></p>
<h1>{html.escape(post["title"])}</h1>
<p class="lede">{html.escape(post["summary"])}</p>
<p class="date"><time datetime="{post["date"]}">{format_date(post["date"])}</time></p>
{render_markdown(post["body"])}
</article></div>"""
    return chrome(page, post["title"], post["description"], canonical, article_ld(post, canonical), main, "article", extra)


def write_posts(posts: list[dict]) -> None:
    blog = ROOT / "blog"
    blog.mkdir(exist_ok=True)
    keep = {post["slug"] for post in posts}
    for child in list(blog.iterdir()):
        if child.is_dir() and child.name not in keep:
            shutil.rmtree(child)
    (blog / "index.html").write_text(render_index(posts), encoding="utf-8")
    for post in posts:
        folder = blog / post["slug"]
        folder.mkdir(exist_ok=True)
        (folder / "index.html").write_text(render_post(post), encoding="utf-8")


def patch_chrome() -> int:
    changed = 0
    for path in sorted(ROOT.rglob("*.html")):
        if "blog" in path.relative_to(ROOT).parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "<nav" not in text and "<footer" not in text:
            continue
        href = rel_to(path, ROOT / "blog" / "index.html")
        head, sep, foot = text.partition("<footer")
        new_head, new_foot = head, foot
        if sep and ">Blog</a>" not in head:
            new_head, count = NAV_RE.subn(
                lambda match: match.group(1) + f'\n<a href="{href}">Blog</a>',
                head,
                count=1,
            )
            if count != 1:
                raise SystemExit(f"could not add Blog to the nav in {path.relative_to(ROOT)}")
        if sep and ">Blog</a>" not in foot:
            new_foot, count = FOOT_RE.subn(
                lambda match: match.group(1) + f'\n<p><a href="{href}">Blog</a></p>',
                foot,
                count=1,
            )
            if count != 1:
                raise SystemExit(f"could not add Blog to the footer in {path.relative_to(ROOT)}")
        updated = new_head + sep + new_foot
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def sitemap_line(loc: str, lastmod: str) -> str:
    return (
        f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
        f"<priority>0.8</priority></url>"
    )


def update_sitemap(posts: list[dict]) -> None:
    path = ROOT / "sitemap.xml"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if "/blog/" not in line]
    newest = posts[0]["date"] if posts else date.today().isoformat()
    entries = [sitemap_line(SITE + "/blog/", newest)]
    for post in sorted(posts, key=lambda item: item["slug"]):
        entries.append(sitemap_line(f"{SITE}/blog/{post['slug']}/", post["date"]))
    for entry in entries:
        loc = entry.split("<loc>", 1)[1].split("</loc>", 1)[0]
        inserted = False
        for index, line in enumerate(lines):
            if "<loc>" not in line:
                continue
            existing = line.split("<loc>", 1)[1].split("</loc>", 1)[0]
            if existing > loc:
                lines.insert(index, entry)
                inserted = True
                break
        if not inserted:
            for index, line in enumerate(lines):
                if line.strip() == "</urlset>":
                    lines.insert(index, entry)
                    inserted = True
                    break
        if not inserted:
            raise SystemExit("sitemap.xml has no urlset close tag")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build() -> None:
    posts = load_posts()
    write_posts(posts)
    patched = patch_chrome()
    update_sitemap(posts)
    print(f"built {len(posts)} post(s); updated nav or footer on {patched} page(s)")


def main() -> int:
    try:
        build()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
