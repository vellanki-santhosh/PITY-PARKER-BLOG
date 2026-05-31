import json
import os
import re
import shutil
import pathlib
from urllib.parse import urlparse

# Optional image resizing (Pillow). If unavailable, script falls back to copying originals.
try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

WORKDIR = pathlib.Path(__file__).resolve().parent
SEED_PATH = WORKDIR / "assets" / "posts-data.js"
PACKAGES_DIR = WORKDIR / "content-packages"
OUT_IMAGES_DIR = WORKDIR / "assets" / "content-images"


def ensure_dir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)


def slug_dir_to_slug(path: pathlib.Path) -> str:
    return path.name


def escape_js_template_literal(html: str) -> str:
    # We embed html in JS template literal: `...`
    # Need to escape backticks and ${ sequences.
    html = html.replace("\\", "\\\\")
    html = html.replace("`", "\\`")
    html = html.replace("${", "\\${")
    return html


def js_date_from_iso(iso: str) -> str:
    # posts-data.js expects: Date.UTC(YYYY, M, D) where M is 0-based.
    # iso looks like: 2022-07-24T00:00:00
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return "Date.UTC(1970, 0, 1)"
    y = int(m.group(1))
    mo = int(m.group(2)) - 1
    d = int(m.group(3))
    return f"Date.UTC({y}, {mo}, {d})"


def read_existing_seed_objects(js_text: str):
    # Very small heuristic: grab between first '[' after window.PP_SEED and matching last '];'
    # since your file is simple.
    start = js_text.find("window.PP_SEED")
    if start == -1:
        raise RuntimeError("Could not find window.PP_SEED")
    bracket_start = js_text.find("[", start)
    bracket_end = js_text.rfind("];", len(js_text))
    if bracket_start == -1 or bracket_end == -1:
        raise RuntimeError("Could not locate PP_SEED array")
    return js_text, bracket_start, bracket_end


def main():
    if not PACKAGES_DIR.exists():
        raise FileNotFoundError(f"Missing {PACKAGES_DIR}")
    ensure_dir(OUT_IMAGES_DIR)

    seed_html = SEED_PATH.read_text(encoding="utf-8")

    # Build map by package slug -> meta
    packages = [p for p in PACKAGES_DIR.iterdir() if p.is_dir()]

    # For merged seed: keep existing posts (user-authored + any non-packaged entries)
    # but replace/augment those that are packaged.
    packaged_by_id = {}
    for pkg in packages:
        meta_path = pkg / "meta.json"
        post_path = pkg / "post.html"
        if not meta_path.exists() or not post_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pkg_slug = meta.get("slug") or slug_dir_to_slug(pkg)
        post_html = post_path.read_text(encoding="utf-8")
        packaged_by_id[meta.get("id")] = {
            "meta": meta,
            "pkg_slug": pkg_slug,
            "post_html": post_html,
            "pkg_dir": pkg,
        }

    if not packaged_by_id:
        raise RuntimeError("No packaged posts found under content-packages")

    # Extract existing objects crudely via regex by id.
    # We'll just rebuild PP_SEED from scratch using the packaged data only,
    # but we must preserve your other posts (like your two full posts already) too.
    # Strategy: use existing SEED entries, and for those with matching ids, inject html.

    # Parse existing JS objects with a regex that grabs id + basic fields.
    # (We don't need perfect JS parsing; we only use it for injection.)
    id_matches = re.findall(r"id:\s*\"([^\"]+)\"", seed_html)
    existing_ids = set(id_matches)

    # If some packaged ids aren't in existing seed, we append them.

    def build_post_object(meta: dict, post_html: str):
        # Ensure required keys exist
        meta.setdefault('slug', slug_dir_to_slug(meta.get('__pkg_dir__', pathlib.Path('.'))))

        # Keep fields if present
        title = meta.get("title") or "Untitled"
        dek = meta.get("dek") or ""
        genre = meta.get("genre") or "Note"
        lang = meta.get("lang") or "en"
        source = meta.get("sourceUrl") or meta.get("source")
        publishedISO = meta.get("publishedISO")

        # Move/copy images into assets/content-images and create responsive variants when possible
        src_img_dir = pathlib.Path(meta.get("assets", {}).get("imagesFolder", "./images"))
        pkg_dir = meta["__pkg_dir__"]
        src_img_abs = pkg_dir / "images"
        target_img_dir = OUT_IMAGES_DIR / (meta.get("slug") or "post") / "images"
        ensure_dir(target_img_dir)
        variants = [480, 800, 1200]
        if src_img_abs.exists():
            for f in src_img_abs.iterdir():
                if f.is_file():
                    dst = target_img_dir / f.name
                    shutil.copy2(f, dst)
                    # create resized variants if Pillow is available and file is an image
                    if HAVE_PIL:
                        try:
                            im = Image.open(f)
                            im_format = 'JPEG'
                            if im.mode in ('RGBA', 'LA'):
                                bg = Image.new('RGB', im.size, (255, 255, 255))
                                bg.paste(im, mask=im.split()[3])
                                im = bg
                            else:
                                im = im.convert('RGB')
                            orig_w, orig_h = im.size
                            stem, _ext = os.path.splitext(f.name)
                            for w in variants:
                                if w >= orig_w:
                                    continue
                                r = w / orig_w
                                nh = int(orig_h * r)
                                resized = im.resize((w, nh), Image.LANCZOS)
                                outname = f"{stem}-w{w}.jpg"
                                resized.save(target_img_dir / outname, format=im_format, quality=82, optimize=True)
                        except Exception:
                            # ignore image processing errors and continue
                            pass

        # Rewrite image src in html to assets/content-images/<slug>/images/<file>
        def rewrite_src_double(mo):
            old = mo.group(1)
            filename = os.path.basename(old)
            slug = meta.get('slug')
            base = f"assets/content-images/{slug}/images/{filename}"
            stem, ext = os.path.splitext(filename)
            srcset_parts = []
            target_dir = OUT_IMAGES_DIR / (slug or "post") / "images"
            if HAVE_PIL and target_dir.exists():
                for entry in target_dir.iterdir():
                    m = re.match(rf"^{re.escape(stem)}-w(\d+)\.jpg$", entry.name)
                    if m:
                        srcset_parts.append((int(m.group(1)), f"assets/content-images/{slug}/images/{entry.name}"))
            # sort by width asc
            srcset_parts.sort()
            if srcset_parts:
                srcset_str = ", ".join([f"{p[1]} {p[0]}w" for p in srcset_parts])
                sizes = "(max-width: 700px) 100vw, 700px"
                return f'src="{base}" srcset="{srcset_str}" sizes="{sizes}"'
            return f'src="{base}"'

        def rewrite_src_single(mo):
            return rewrite_src_double(mo).replace('"', "'")

        rewritten = re.sub(r'src="\.\/images\/([^\"]+)"', rewrite_src_double, post_html)
        rewritten = re.sub(r"src='\.\/images\/([^\']+)'", rewrite_src_single, rewritten)

        html_escaped = escape_js_template_literal(rewritten)

        date_expr = js_date_from_iso(publishedISO or "1970-01-01")

        # Ensure escaped HTML is wrapped in a JS template literal.
        # NOTE: We MUST include the actual `html: `...`` field in output.
        lines = [
            "  {",
            f"    id: {json.dumps(meta.get('id'))},",
            f"    title: {json.dumps(title)},",
            f"    dek: {json.dumps(dek)},",
            f"    genre: {json.dumps(genre)},",
            f"    lang: {json.dumps(lang)},",
            f"    date: {date_expr},",
            f"    source: {json.dumps(source)},",
            "    html: `",
            html_escaped,
            "`,",
            "  }",
        ]
        return "\n".join(lines)

    # Inject by id into existing PP_SEED by rebuilding whole array from packaged posts + existing posts.
    # Simpler and safe: rebuild PP_SEED from scratch using existing seed ids order but with html when packaged.

    # Extract existing seed objects by splitting on '\n  {' boundaries.
    # We'll rebuild by parsing ids from existing seed and replacing html when possible.

    start = seed_html.find("window.PP_SEED")
    bracket_start = seed_html.find("[", start)
    bracket_end = seed_html.rfind("];", len(seed_html))

    before = seed_html[:bracket_start+1]
    after = "];\n"

    # Get objects by ids in order they appear.
    obj_splits = re.split(r"\n\s*\/\* ----------", seed_html)
    # fallback: just find id occurrences and build order from that
    ordered_ids = re.findall(r"id:\s*\"([^\"]+)\"", seed_html)
    ordered_ids_unique = []
    for i in ordered_ids:
        if i not in ordered_ids_unique:
            ordered_ids_unique.append(i)

    output_objects = []

    packaged_ids = set(packaged_by_id.keys())

    # Helper to reuse existing object skeleton (without html injection)
    # If id is packaged, we build full object.
    for id_ in ordered_ids_unique:
        pkg = packaged_by_id.get(id_)
        if pkg:
            m = pkg["meta"].copy()
            m["__pkg_dir__"] = pkg["pkg_dir"]
            output_objects.append(build_post_object(m, pkg["post_html"]))
        else:
            # Keep existing entries as-is by extracting from seed_html via id-based regex block
            # We'll do a conservative extraction: take from 'id: "..."' line up to next '},' or ']' boundary.
            # Simpler: don't keep; instead we will append at the end.
            pass

    # Append any packaged posts that were not in existing ordered_ids
    missing = [pid for pid in packaged_by_id.keys() if pid not in set(ordered_ids_unique)]
    for pid in missing:
        pkg = packaged_by_id[pid]
        m = pkg["meta"].copy()
        m["__pkg_dir__"] = pkg["pkg_dir"]
        output_objects.append(build_post_object(m, pkg["post_html"]))

    new_seed = before + "\n\n" + (",\n\n".join(output_objects)) + "\n\n" + after
    SEED_PATH.write_text(new_seed, encoding="utf-8")
    print(f"Wrote updated {SEED_PATH} with {len(output_objects)} posts (html injected).")


if __name__ == "__main__":
    main()

