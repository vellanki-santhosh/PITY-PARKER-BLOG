import os
import re
import json
import hashlib
import pathlib
import shutil
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


WORKDIR = pathlib.Path(__file__).resolve().parent
SEED_JS_PATH = WORKDIR / "assets" / "posts-data.js"
OUT_DIR = WORKDIR / "content-packages"

# Keep downloads manageable
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "post"


def build_post_slug(post: dict, idx: int) -> str:
    # Prefer the title when it yields a useful ASCII slug, but fall back to
    # the stable id for non-Latin titles so packages stay distinct.
    title_slug = slugify(post.get("title") or "")
    if title_slug != "post":
        return title_slug

    id_slug = slugify(post.get("id") or "")
    if id_slug != "post":
        return id_slug

    return f"post-{idx}"


def http_get(url: str, session: requests.Session) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = session.get(url, headers=headers, timeout=45, verify=False)
    r.raise_for_status()
    return r.text


def extract_seed_posts(js_text: str):
    # Pull window.PP_SEED = [ ... ]; content.
    m = re.search(r"window\.PP_SEED\s*=\s*\[(.*?)]\s*;\s*$", js_text, flags=re.S | re.M)
    if not m:
        # Fallback: try to locate start/end of PP_SEED array more robustly
        start = js_text.find("window.PP_SEED")
        if start == -1:
            raise RuntimeError("Could not find window.PP_SEED in posts-data.js")
        bracket_start = js_text.find("[", start)
        bracket_end = js_text.rfind("];", len(js_text))
        if bracket_start == -1 or bracket_end == -1:
            raise RuntimeError("Could not parse PP_SEED array bounds")
        array_text = js_text[bracket_start + 1: bracket_end]
        wrapped = "[" + array_text + "]"
    else:
        wrapped = "[" + m.group(1) + "]"

    # Convert JS array to JSON-ish by evaluating template literals is hard.
    # However, the existing seed uses html: `...` backticks.
    # We will NOT fully parse; instead we will extract objects via a lightweight heuristic:
    # We capture each top-level `{ ... }` object in the array and then parse known fields with regex.

    # This script supports: id,title,dek,genre,lang,date,source,archive,excerpt,html.
    # For full 'html' we won't scrape; only for posts where source exists.

    objects = []
    # Find each object that starts with { and ends with }, at nesting depth 0.
    depth = 0
    in_str = False
    str_ch = ""
    buf = []

    # naive scanner for top-level objects inside the array text
    i = 0
    array_body = wrapped
    # locate top-level { ... }
    for idx, ch in enumerate(array_body):
        pass

    def scan_objects(s: str):
        objs = []
        depth = 0
        in_tmpl = False
        in_squote = False
        in_dquote = False
        start = None
        for i, ch in enumerate(s):
            # toggle string states
            if in_tmpl:
                if ch == "`":
                    in_tmpl = False
                continue
            if in_squote:
                if ch == "'" and (i == 0 or s[i-1] != "\\"):
                    in_squote = False
                continue
            if in_dquote:
                if ch == '"' and (i == 0 or s[i-1] != "\\"):
                    in_dquote = False
                continue

            if ch == "`":
                in_tmpl = True
                continue
            if ch == "'":
                in_squote = True
                continue
            if ch == '"':
                in_dquote = True
                continue

            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    objs.append(s[start:i+1])
                    start = None
        return objs

    object_texts = scan_objects(array_body)

    def extract_js_string(pattern: str, text: str):
        m = re.search(pattern, text, flags=re.S)
        if not m:
            return None
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        if raw is None:
            return None
        return raw.replace(r"\\", "\\").replace(r'\"', '"').replace(r"\'", "'")

    key_regexes = {
        "id": r"\bid\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "title": r"\btitle\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "dek": r"\bdek\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "genre": r"\bgenre\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "lang": r"\blang\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "source": r"\bsource\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
        "archive": r"\barchive\s*:\s*(true|false)",
        "excerpt": r"\bexcerpt\s*:\s*(?:'((?:\\.|[^'])*)'|\"((?:\\.|[^\"])*)\")",
    }

    date_regex = r"\bdate\s*:\s*Date\.UTC\(([^\)]*)\)"

    def parse_date(s: str):
        m = re.search(date_regex, s)
        if not m:
            return None
        args = [a.strip() for a in m.group(1).split(",")]
        # Expect: Date.UTC(YYYY, M, D)
        try:
            year = int(args[0])
            month = int(args[1])
            day = int(args[2])
            # to ISO date (month is 0-based)
            dt = datetime(year, month + 1, day)
            published_iso = dt.replace(tzinfo=datetime.utcnow().astimezone().tzinfo).isoformat()
            published_display = dt.strftime("%d %B %Y")
            return {
                "publishedISO": dt.isoformat(),
                "publishedDisplay": published_display,
            }
        except Exception:
            return None

    for ot in object_texts:
        obj = {}
        for k, rx in key_regexes.items():
            if k == "archive":
                mm = re.search(rx, ot)
                if mm:
                    obj[k] = mm.group(1)
                continue
            value = extract_js_string(rx, ot)
            if value is not None:
                obj[k] = value
        m_date = re.search(date_regex, ot)
        if m_date:
            # store raw date args as well
            args = [a.strip() for a in m_date.group(1).split(",")]
            obj["date"] = "Date.UTC(" + m_date.group(1) + ")"
            try:
                year = int(args[0])
                month = int(args[1])
                day = int(args[2])
                dt = datetime(year, month + 1, day)
                obj["publishedISO"] = dt.isoformat()
                obj["publishedDisplay"] = dt.strftime("%d %B %Y")
            except Exception:
                pass

        # html/excerpt in JS might contain newlines/quotes; we skip deeper parsing.
        objects.append(obj)

    # Filter out ones without id
    return [o for o in objects if o.get("id")]


def pick_main_body(soup: BeautifulSoup):
    # Heuristics for Blogspot-like pages.
    # Prefer <article>, then #content, then .post-body.
    candidates = [
        soup.find("article"),
        soup.find(id="content"),
        soup.select_one(".post-body"),
        soup.select_one(".post-content"),
        soup.select_one("main"),
    ]
    for c in candidates:
        if c and c.get_text(strip=True):
            return c

    # Fallback: longest text container
    best = None
    best_len = 0
    for tag in soup.find_all(["div", "article", "main"]):
        txt = tag.get_text(" ", strip=True)
        l = len(txt)
        if l > best_len:
            best_len = l
            best = tag
    return best


def download_binary(url: str, session: requests.Session) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    r = session.get(url, headers=headers, timeout=60, stream=True)
    r.raise_for_status()
    content = r.content
    return content


def ensure_dir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)


def safe_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
        return ext
    return ".jpg"


def unique_filename(original_url: str, index: int) -> str:
    ext = safe_ext_from_url(original_url)
    h = hashlib.sha1(original_url.encode("utf-8")).hexdigest()[:10]
    return f"img_{index}_{h}{ext}"


def rewrite_images_and_collect(html_el, page_url: str, session: requests.Session, img_out_dir: pathlib.Path):
    # Collect and rewrite all <img src="..."> inside html_el
    for i, img in enumerate(html_el.find_all("img")):
        src = img.get("src")
        if not src:
            continue
        abs_src = urljoin(page_url, src)

        try:
            content = download_binary(abs_src, session)
            if len(content) > MAX_IMAGE_BYTES:
                # Skip large images but keep original src
                continue
            filename = unique_filename(abs_src, i)
            out_path = img_out_dir / filename
            out_path.write_bytes(content)

            # Rewrite
            img["src"] = str(pathlib.Path("./images").joinpath(filename)).replace("\\", "/")
            # Keep alt as-is; if missing, try from data- attributes
            if not img.get("alt"):
                alt = img.get("title") or ""
                img["alt"] = alt
        except Exception:
            # If download fails, leave src untouched
            continue

    return html_el


def main():
    if not SEED_JS_PATH.exists():
        raise FileNotFoundError(f"Missing {SEED_JS_PATH}")

    js_text = SEED_JS_PATH.read_text(encoding="utf-8")
    posts = extract_seed_posts(js_text)

    # Only scrape those that have a source
    to_scrape = [p for p in posts if p.get("source")]
    if not to_scrape:
        raise RuntimeError("No posts with 'source' found. Nothing to scrape.")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    ensure_dir(OUT_DIR)
    session = requests.Session()

    for idx, p in enumerate(to_scrape, start=1):
        source_url = p["source"]
        post_slug = build_post_slug(p, idx)
        pkg_dir = OUT_DIR / post_slug
        ensure_dir(pkg_dir)
        img_dir = pkg_dir / "images"
        ensure_dir(img_dir)
        media_dir = pkg_dir / "media"
        ensure_dir(media_dir)

        print(f"[{idx}/{len(to_scrape)}] Scraping: {p.get('title')}\n  {source_url}")

        page_html = http_get(source_url, session)
        soup = BeautifulSoup(page_html, "html.parser")

        body = pick_main_body(soup)
        if not body:
            raise RuntimeError(f"Could not extract main body for {source_url}")

        # Rewrite images to local
        rewrite_images_and_collect(body, source_url, session, img_dir)

        # Serialize body HTML
        body_html = str(body)

        # Save
        post_html_path = pkg_dir / "post.html"
        post_html_path.write_text(body_html, encoding="utf-8")

        meta = {
            "id": p.get("id"),
            "title": p.get("title"),
            "publishedISO": p.get("publishedISO"),
            "publishedDisplay": p.get("publishedDisplay"),
            "authorName": "Pity Parker",
            "sourceUrl": source_url,
            "slug": post_slug,
            "assets": {
                "imagesFolder": "./images",
                "mediaEmbedsFolder": "./media",
            },
        }
        meta_path = pkg_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Done. Packages created in: "+str(OUT_DIR))


if __name__ == "__main__":
    main()

