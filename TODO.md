# TODO — blog post packaging (from remote URLs)

- [ ] Confirm extraction target: scrape full article HTML from the `source` URLs in `assets/posts-data.js` (Option B)
- [x] Implement a Python script that:
  - [x] Loads `assets/posts-data.js` and reads `window.PP_SEED` post metadata
  - [x] For each post with `source`, downloads the page HTML
  - [x] Extracts the main article/body content (heuristic selectors)
  - [x] Downloads images to `content-packages/<post-slug>/images/` and rewrites image `src` in `post.html`
  - [x] Writes `content-packages/<post-slug>/post.html` and `meta.json`
  - [ ] Writes `content-packages/<post-slug>/media/embeds.md` if embeds are present
- [ ] Add a small README with run instructions
- [x] Run the script and validate output for all posts (packages created in `content-packages/`)

