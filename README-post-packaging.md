# Post packaging (scrape + localize assets)

This script creates a folder per blog post so you can paste its content into `post-template.html` without losing media.

## What it does
- Reads `window.PP_SEED` from `assets/posts-data.js`
- For each post that has a `source` URL:
  - Downloads the page HTML
  - Extracts the main body (heuristic selectors)
  - Downloads images found in that body into `images/`
  - Rewrites `img src` paths in the extracted body to point to local files
  - Writes:
    - `content-packages/<slug>/post.html`
    - `content-packages/<slug>/meta.json`

## Install dependencies
```bat
cd "c:/Users/vella/Downloads/PITY PARKER BLOG"
py -m pip install -r requirements.txt
```

## Run
```bat
cd "c:/Users/vella/Downloads/PITY PARKER BLOG"
py package_posts.py
```

## Output structure
- `content-packages/<post-slug>/post.html`
- `content-packages/<post-slug>/meta.json`
- `content-packages/<post-slug>/images/*`

## Notes
- The script currently uses `verify=False` in requests to bypass a broken CA bundle on this machine. After you fix CA verification, you can flip it back to `verify=True`.

