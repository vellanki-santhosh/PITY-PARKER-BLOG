import html
import json
import pathlib
import re
import shutil
from datetime import datetime


WORKDIR = pathlib.Path(__file__).resolve().parent
PACKAGES_DIR = WORKDIR / "content-packages"
POSTS_DIR = WORKDIR / "posts"


def ensure_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def slug_from_meta(meta: dict, fallback: str) -> str:
    slug = (meta.get("slug") or fallback or "post").strip().strip("/")
    return slug or fallback or "post"


def reading_time_from_html(post_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", post_html or "")
    words = len([word for word in text.split() if word])
    return f"{max(1, round(words / 200))} min read"


def build_page(meta: dict, post_html: str, og_image: str = "", page_url: str = "") -> str:
    title = html.escape(meta.get("title") or "Untitled Post")
    author = html.escape(meta.get("authorName") or "Pity Parker")
    published = html.escape(meta.get("publishedDisplay") or "")
    published_iso = html.escape(meta.get("publishedISO") or "")
    genre = html.escape(meta.get("genre") or "Blog")
    source_url = html.escape(meta.get("sourceUrl") or "https://pityparker.blogspot.com/")
    summary = html.escape(meta.get("summary") or "An archived post from Pity Parker's blog.")
    reading_time = reading_time_from_html(post_html)

    year = datetime.now().year

    page = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>%%TITLE%% | Pity Parker</title>
  <meta name="description" content="%%SUMMARY%%" />
  <link rel="canonical" href="%%CANONICAL%%" />

  <!-- Open Graph / Twitter -->
  <meta property="og:title" content="%%TITLE%%" />
  <meta property="og:description" content="%%SUMMARY%%" />
  <meta property="og:image" content="%%OG_IMAGE%%" />
  <meta property="og:url" content="%%PAGE_URL%%" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="%%TITLE%%" />
  <meta name="twitter:description" content="%%SUMMARY%%" />
  <meta name="twitter:image" content="%%OG_IMAGE%%" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&family=Spectral:ital,wght@0,300;0,400;0,500;0,600;1,400;1,500&family=Hanken+Grotesk:wght@400;500;600;700&family=Noto+Serif+Telugu:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../../assets/styles.css" />
  <style>
    .post-page { background: var(--paper); }
    .post-page main { display:block; }
    .post-page .page-shell { max-width: 1000px; margin: 0 auto; padding: 28px 20px 80px; }
    .post-page .post-shell { display:grid; gap:22px; }
    .post-page header.post-header, .post-page .post-body-card, .post-page section.comments { background: var(--paper-card); border: 1px solid var(--hairline); border-radius: 8px; }
    .post-page header.post-header { padding: 22px; }
    .post-page .post-title { font-family: var(--display); font-size: clamp(30px, 5vw, 58px); line-height: 1.04; margin-bottom: 12px; }
    .post-page .post-meta { display:flex; flex-wrap:wrap; gap: 12px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--hairline); padding-top: 12px; }
    .post-page .post-body-card { padding: 26px; }
    .post-page article.post-content { max-width: 760px; margin: 0 auto; }
    .post-page .post-text { line-height: 1.82; font-size: 19px; color: var(--ink-soft); }
    .post-page .post-text p, .post-page .post-text div, .post-page .post-text blockquote { margin-bottom: 18px; }
    .post-page .post-text img { max-width: 100%; height: auto; border-radius: 6px; }
    .post-page .comments { padding: 22px; }
    .post-page .comments-title { display:flex; align-items:center; gap:10px; margin-bottom: 14px; }
    .post-page .comments-list, .post-page .comment-form { background: #fff; border: 1px solid var(--hairline); border-radius: 6px; padding: 16px; }
    .post-page .comments-list { margin-bottom: 16px; }
    .post-page .comment { padding: 12px 0; border-bottom: 1px solid var(--hairline); }
    .post-page .comment:last-child { border-bottom: none; }
    .post-page .field { display:flex; flex-direction:column; gap:8px; margin-bottom: 14px; }
    .post-page .field label { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); font-weight: 700; }
    .post-page .field input, .post-page .field textarea { border: 1px solid var(--hairline); border-radius: 6px; padding: 10px 12px; font-size: 16px; background: transparent; color: var(--ink); }
    .post-page .actions { display:flex; gap: 12px; align-items:center; flex-wrap: wrap; }
    .post-page button { border: 1px solid var(--ink); background: var(--ink); color: var(--paper); padding: 10px 14px; border-radius: 6px; cursor: pointer; font-weight: 700; }
    .post-page button.secondary { background: transparent; color: var(--ink); border-color: var(--hairline); }
    @media (max-width: 700px) {
      .post-page .page-shell { padding-left: 14px; padding-right: 14px; }
      .post-page .post-body-card, .post-page header.post-header, .post-page section.comments { border-radius: 4px; }
    }
  </style>
  </head>
<body class="post-page">
  <header class="site-header">
    <nav class="nav" aria-label="Primary">
      <a href="../../index.html#top" class="brand"><span class="dot"></span>Pity Parker</a>
      <div class="nav-links" id="navLinks">
        <a href="../../index.html#top">Home</a>
        <a href="../../index.html#blog">Blog</a>
        <a href="../../index.html#about">About</a>
        <a href="../../index.html#contact">Contact</a>
      </div>
      <button class="nav-write" id="openComposer" type="button" onclick="window.location.href='../../index.html#blog'"><i class="fa-solid fa-feather-pointed"></i> Write a post</button>
      <button class="menu-toggle" id="menuToggle" aria-label="Menu" type="button" onclick="window.location.href='../../index.html#blog'"><i class="fa-solid fa-bars"></i></button>
    </nav>
  </header>

  <main id="top">
    <div class="page-shell">
      <div class="post-shell">
        <header class="post-header" aria-label="Post metadata">
          <h1 class="post-title">%%TITLE%%</h1>
          <div class="post-meta">
            <time class="post-date" datetime="%%PUBLISHED_ISO%%">%%PUBLISHED%%</time>
            <span aria-hidden="true">·</span>
            <span class="post-author">By <strong>%%AUTHOR%%</strong></span>
            <span aria-hidden="true">·</span>
            <span class="post-reading-time">%%READING_TIME%%</span>
            <span aria-hidden="true">·</span>
            <span class="post-genre">%%GENRE%%</span>
          </div>
        </header>

        <div class="post-body-card">
          <article class="post-content" aria-label="Full post content">
            <section class="post-text" aria-label="Body">%%POST_HTML%%</section>
          </article>
        </div>

        <section class="comments" aria-label="Comments section">
          <div class="comments-title">
            <span style="color:var(--ochre);font-weight:800;">●</span>
            <h2 style="font-size:18px;">Comments</h2>
            <span style="margin-left:auto;color:var(--muted);font-size:14px;">No comments yet</span>
          </div>
          <div class="comments-list" role="list" aria-label="List of comments">
            <p style="color:var(--muted);">This post is published as a standalone page. Comment integration can be added later.</p>
          </div>
          <form class="comment-form" action="#" method="post" aria-label="Submit a comment">
            <div class="field">
              <label for="commentName">Name</label>
              <input id="commentName" name="name" type="text" placeholder="Your name" autocomplete="name" />
            </div>
            <div class="field">
              <label for="commentEmail">Email</label>
              <input id="commentEmail" name="email" type="email" placeholder="you@example.com" autocomplete="email" />
            </div>
            <div class="field">
              <label for="commentBody">Comment</label>
              <textarea id="commentBody" name="body" rows="5" placeholder="Write your comment…"></textarea>
            </div>
            <div class="actions">
              <button type="submit">Post Comment</button>
              <button type="button" class="secondary">Reset</button>
            </div>
          </form>
        </section>
      </div>
    </div>
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="fbrand">Pity Parker</div>
      <div class="fcopy">© %%YEAR%% Pity Parker · Poet, Author &amp; Translator · Built with <a href="../../index.html#top">care</a></div>
    </div>
  </footer>
</body>
</html>
"""

    return (
        page.replace("%%TITLE%%", title)
        .replace("%%SUMMARY%%", summary)
        .replace("%%SOURCE_URL%%", source_url)
        .replace("%%PUBLISHED_ISO%%", published_iso)
        .replace("%%PUBLISHED%%", published)
        .replace("%%AUTHOR%%", author)
        .replace("%%READING_TIME%%", reading_time)
        .replace("%%GENRE%%", genre)
        .replace("%%YEAR%%", str(year))
        .replace("%%POST_HTML%%", post_html)
      .replace("%%OG_IMAGE%%", html.escape(og_image or "../../assets/img/book-cover.png"))
      .replace("%%CANONICAL%%", html.escape(page_url or source_url))
      .replace("%%PAGE_URL%%", html.escape(page_url or source_url))
    )


def main() -> None:
    if not PACKAGES_DIR.exists():
        raise FileNotFoundError(f"Missing {PACKAGES_DIR}")

    if POSTS_DIR.exists():
        shutil.rmtree(POSTS_DIR)
    ensure_dir(POSTS_DIR)

    written = 0
    for pkg in sorted([path for path in PACKAGES_DIR.iterdir() if path.is_dir()]):
        meta_path = pkg / "meta.json"
        post_path = pkg / "post.html"
        if not meta_path.exists() or not post_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        slug = slug_from_meta(meta, pkg.name)
        page_dir = POSTS_DIR / slug
        ensure_dir(page_dir)

        src_images = pkg / "images"
        if src_images.exists():
            dst_images = page_dir / "images"
            ensure_dir(dst_images)
            for image_file in src_images.iterdir():
                if image_file.is_file():
                    shutil.copy2(image_file, dst_images / image_file.name)

        # choose an OG image: first copied image in the page folder if present
        og_image_rel = "../../assets/img/book-cover.png"
        dst_images = page_dir / "images"
        if dst_images.exists():
          imgs = [p for p in dst_images.iterdir() if p.is_file()]
          if imgs:
            og_image_rel = "./images/" + imgs[0].name

        page_html = build_page(meta, post_path.read_text(encoding="utf-8"), og_image_rel, f"https://pityparker.com/posts/{slug}/")
        (page_dir / "index.html").write_text(page_html, encoding="utf-8")
        written += 1

    print(f"Wrote {written} standalone post pages in {POSTS_DIR}")


if __name__ == "__main__":
    main()