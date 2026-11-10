#!/usr/bin/env python3
"""Checks for the static blog build."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_blog  # noqa: E402

POST = ROOT / "blog" / "homeschool-psat-prep-12-week-plan" / "index.html"
SOURCE = ROOT / "posts" / "homeschool-psat-prep-12-week-plan.md"
ETSY = "https://www.etsy.com/listing/4587938543"


class BlogBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_blog.build()

    def test_word_count_and_voice(self):
        post = build_blog.load_posts()[0]
        count = build_blog.word_count(post["body"])
        self.assertGreaterEqual(count, 1200)
        self.assertLessEqual(count, 1600)
        self.assertNotIn("!", post["body"])
        self.assertNotIn("\u2014", post["body"])
        self.assertNotIn("\u2013", post["body"])
        visible = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", post["body"])
        visible = re.sub(r"<[^>]+>", " ", visible)
        self.assertNotRegex(visible, r"diagnostic")
        self.assertLessEqual(len(post["description"]), 170)
        self.assertGreaterEqual(len(post["description"]), 50)
        self.assertEqual(post["slug"], "homeschool-psat-prep-12-week-plan")

    def test_pages_and_seo(self):
        index = (ROOT / "blog" / "index.html").read_text(encoding="utf-8")
        post = POST.read_text(encoding="utf-8")
        self.assertIn("<h1>Blog</h1>", index)
        self.assertIn("homeschool-psat-prep-12-week-plan/", index)
        self.assertIn('rel="canonical" href="https://homeschoolaitutor.com/blog/"', index)
        self.assertIn(
            'rel="canonical" href="https://homeschoolaitutor.com/blog/homeschool-psat-prep-12-week-plan/"',
            post,
        )
        self.assertIn('meta property="og:type" content="article"', post)
        self.assertIn('meta name="description"', post)
        self.assertEqual(post.count(ETSY), 2)
        self.assertIn("/diagnostics/psat-placement-diagnostic.html", post)
        self.assertIn("PSAT placement check", post)
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', post).group(1)
        data = json.loads(raw)
        article = next(node for node in data["@graph"] if node["@type"] == "Article")
        self.assertEqual(article["headline"], "Homeschool PSAT Prep: A 12-Week Study Plan")
        self.assertEqual(article["datePublished"], "2026-11-10")
        self.assertIn("publisher", article)
        self.assertIn("<table>", post)
        self.assertIn("<time datetime=\"2026-11-10\">", post)

    def test_sitemap_and_nav(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://homeschoolaitutor.com/blog/</loc>", sitemap)
        self.assertEqual(
            sitemap.count("<loc>https://homeschoolaitutor.com/blog/homeschool-psat-prep-12-week-plan/</loc>"),
            1,
        )
        self.assertEqual(sitemap.count("<loc>https://homeschoolaitutor.com/blog/"), 2)
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="blog/index.html">Blog</a>', home)
        nested = (ROOT / "packs" / "psat-prep-12wk.html").read_text(encoding="utf-8")
        self.assertIn('href="../blog/index.html">Blog</a>', nested)
        missing = [
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*.html")
            if ">Blog</a>" not in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(missing, [])

    def test_markdown_and_drafts(self):
        html_out = build_blog.render_markdown(
            "See **this** and [the plan](https://example.com/a).\n\n- one\n- two\n"
        )
        self.assertIn("<strong>this</strong>", html_out)
        self.assertIn('href="https://example.com/a"', html_out)
        self.assertIn("<li>one</li>", html_out)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "draft.md").write_text(
                "---\ntitle: Draft\ndescription: d\ndate: 2026-11-01\n"
                "slug: draft-post\nsummary: s\ndraft: true\n---\n\nHidden.\n",
                encoding="utf-8",
            )
            (folder / "live.md").write_text(
                "---\ntitle: Live\ndescription: d\ndate: 2026-10-01\n"
                "slug: live-post\nsummary: s\n---\n\nShown.\n",
                encoding="utf-8",
            )
            posts = build_blog.load_posts(folder)
            self.assertEqual([post["slug"] for post in posts], ["live-post"])

    def test_rebuild_is_stable(self):
        before = POST.read_text(encoding="utf-8")
        build_blog.build()
        self.assertEqual(POST.read_text(encoding="utf-8"), before)
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count("/blog/"), 2)


if __name__ == "__main__":
    unittest.main()
