/* ============================================================
   Pity Parker — site logic
   Posts, composer, reader, navigation
   ============================================================ */
(function () {
  "use strict";

  /* ---------- tiny helpers ---------- */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const STORE_KEY = "pp_posts_v2";
  const OLD_KEYS = ["pp_posts_v1"];
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  function uid() { return "p_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

  function fmtDate(ts) {
    try {
      return new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    } catch (e) { return ""; }
  }
  function readingTime(text) {
    const words = (text || "").trim().split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.round(words / 200));
  }
  function paragraphs(text) {
    return String(text || "")
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);
  }
  function stripTags(html) {
    const d = document.createElement("div");
    d.innerHTML = html || "";
    return d.textContent || "";
  }
  function postText(p) {
    if (p.body) return p.body;
    if (p.html) return stripTags(p.html);
    return (p.excerpt || "") + " " + (p.dek || "");
  }
  function slugify(s) {
    return String(s == null ? "" : s).trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "") || "post";
  }
  function postPageUrl(p) {
    if (!p || !p.source) return "";
    const titleSlug = slugify(p.title);
    const idSlug = slugify(p.id);
    const slug = titleSlug !== "post" ? titleSlug : idSlug;
    return `posts/${slug}/index.html`;
  }

  /* ---------- seed posts (imported from posts-data.js) ---------- */
  const SEED = Array.isArray(window.PP_SEED) ? window.PP_SEED : [];

  /* ---------- storage (with migration that keeps the author's own posts) ---------- */
  function loadPosts() {
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem(STORE_KEY)); } catch (e) {}
    if (Array.isArray(raw)) return raw;

    // First run on this version: start from the imported blog content,
    // and carry over any posts the author wrote under an older version.
    let userPosts = [];
    OLD_KEYS.forEach((k) => {
      try {
        const old = JSON.parse(localStorage.getItem(k));
        if (Array.isArray(old)) {
          userPosts = userPosts.concat(old.filter((p) => p && typeof p.id === "string" && p.id.indexOf("p_") === 0));
        }
      } catch (e) {}
    });
    const seeded = userPosts.concat(SEED.map((p) => Object.assign({}, p)));
    savePosts(seeded);
    return seeded;
  }
  function savePosts(arr) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(arr)); return true; }
    catch (e) {
      toast("Couldn't save — the photo may be too large. Try a smaller image.");
      return false;
    }
  }
  let POSTS = loadPosts();

  /* ============================================================
     Render post list
     ============================================================ */
  const postList = $("#postList");
  const archiveGrid = $("#archiveGrid");
  function renderList() {
    const sorted = POSTS.slice().sort((a, b) => b.date - a.date);
    if (!sorted.length) {
      postList.innerHTML = '<p class="writing-empty">No posts yet. Press “Write a post” to publish your first one.</p>';
      if (archiveGrid) {
        archiveGrid.innerHTML = '<p class="writing-empty">No imported archive entries are available.</p>';
      }
      return;
    }

    // Separate author-created posts (drafts/published from composer) from imported seed HTML posts.
    const authorPosts = sorted.filter((p) => p && typeof p.id === 'string' && p.id.indexOf('p_') === 0);
    const importedPosts = sorted.filter((p) => !p || !p.id || (typeof p.id === 'string' && p.id.indexOf('p_') !== 0)).filter(Boolean);

    // Render author posts in the main writing list
    postList.innerHTML = (authorPosts.length ? authorPosts : []).map((p) => {
      const langClass = p.lang === "te" ? "te" : "";
      const thumb = p.image
        ? `<img class="pc-thumb" src="${esc(p.image)}" alt="">`
        : "";
      const rt = readingTime(postText(p));
      const pageUrl = postPageUrl(p);
      const cardTagOpen = pageUrl ? `<a class="post-card" href="${esc(pageUrl)}">` : `<article class="post-card" data-id="${esc(p.id)}">`;
      const cardTagClose = pageUrl ? `</a>` : `</article>`;
      return `
        ${cardTagOpen}
          <div class="pc-date">${fmtDate(p.date)}<span class="pc-genre">${esc(p.genre || "Note")}</span></div>
          <div class="pc-body">
            <h3 class="pc-title ${langClass}">${esc(p.title)}</h3>
            ${p.dek ? `<p class="pc-dek ${langClass}">${esc(p.dek)}</p>` : ""}
          </div>
          ${thumb || `<div class="pc-read">${rt} min read <span class="pc-arrow"><i class="fa-solid fa-arrow-right"></i></span></div>`}
        ${cardTagClose}`;
    }).join("");

    $$(".post-card[data-id]", postList).forEach((card) => {
      card.addEventListener("click", () => openReader(card.dataset.id));
    });

    if (archiveGrid) {
      archiveGrid.innerHTML = (importedPosts.length ? importedPosts : []).map((p) => {
        const langClass = p.lang === "te" ? "te" : "";
        const summary = p.dek || (p.archive ? p.excerpt : stripTags((p.html || p.body || "")).slice(0, 180));
        const hasImage = !!p.image;
        const pageUrl = postPageUrl(p);
        const openTag = pageUrl ? `<a class="archive-card" href="${esc(pageUrl)}">` : `<article class="archive-card" data-id="${esc(p.id)}">`;
        const closeTag = pageUrl ? `</a>` : `</article>`;
        return `
          ${openTag}
            ${hasImage ? `<div class="archive-thumb"><img src="${esc(p.image)}" alt=""></div>` : ""}
            <div class="archive-copy">
              <div class="archive-meta">${fmtDate(p.date)}<span>${esc(p.genre || "Note")}</span></div>
              <h3 class="archive-title ${langClass}">${esc(p.title)}</h3>
              ${summary ? `<p class="archive-summary ${langClass}">${esc(summary)}</p>` : ""}
              ${pageUrl ? `<span class="archive-open">Read post <i class="fa-solid fa-arrow-right"></i></span>` : `<button class="archive-open" type="button">Read post <i class="fa-solid fa-arrow-right"></i></button>`}
            </div>
          ${closeTag}`;
      }).join("");

      $$(".archive-card[data-id]", archiveGrid).forEach((card) => {
        card.addEventListener("click", () => openReader(card.dataset.id));
      });
    }
  }

  /* ============================================================
     Reader overlay
     ============================================================ */
  const readerOverlay = $("#readerOverlay");
  const readerContent = $("#readerContent");
  function openReader(id) {
    const p = POSTS.find((x) => x.id === id);
    if (!p) return;
    const langClass = p.lang === "te" ? "te" : "";
    let contentHtml;
    if (p.html) {
      contentHtml = p.html;
    } else if (p.archive) {
      contentHtml = `<p class="r-lead">${esc(p.excerpt || "")}</p>`;
    } else {
      contentHtml = paragraphs(p.body).map((t) => `<p>${esc(t)}</p>`).join("");
    }
    const sourceLink = p.source
      ? `<a class="r-source" href="${esc(p.source)}" target="_blank" rel="noopener"><i class="fa-solid fa-up-right-from-square"></i> ${p.archive ? "Read the full piece on the original blog" : "View the original post"}</a>`
      : "";
    const canEdit = !!p.body && !p.html && !p.archive;
    readerContent.innerHTML = `
      <div class="r-genre">${esc(p.genre || "Note")}</div>
      <h1 class="${langClass}">${esc(p.title)}</h1>
      ${p.dek ? `<p class="r-dek ${langClass}">${esc(p.dek)}</p>` : ""}
      <div class="r-meta">
        <img class="avatar" src="assets/img/author.png" alt="Pity Parker">
        <span>By Pity Parker</span>
        <span>·</span>
        <span>${fmtDate(p.date)}</span>
        ${p.archive ? "" : `<span>·</span><span>${readingTime(postText(p))} min read</span>`}
      </div>
      ${p.image ? `<img class="r-img" src="${esc(p.image)}" alt="">` : ""}
      <div class="r-content ${langClass}">${contentHtml}</div>
      ${sourceLink ? `<div class="r-source-row">${sourceLink}</div>` : ""}
      <div class="r-edit-row">
        ${canEdit ? `<button class="btn ghost" data-edit="${esc(p.id)}"><i class="fa-solid fa-pen ico"></i> Edit this post</button>` : ""}
        <button class="btn ghost" data-del="${esc(p.id)}"><i class="fa-solid fa-trash ico"></i> Delete</button>
      </div>`;
    const editBtn = $("[data-edit]", readerContent);
    if (editBtn) editBtn.addEventListener("click", (e) => {
      closeReader();
      openComposer(e.currentTarget.dataset.edit);
    });
    $("[data-del]", readerContent).addEventListener("click", (e) => {
      if (confirm("Delete this post? This can't be undone.")) {
        POSTS = POSTS.filter((x) => x.id !== e.currentTarget.dataset.del);
        savePosts(POSTS);
        renderList();
        closeReader();
        toast("Post deleted.");
      }
    });
    openOverlay(readerOverlay);
    readerOverlay.scrollTop = 0;
  }
  function closeReader() { closeOverlay(readerOverlay); }

  /* ============================================================
     Composer overlay
     ============================================================ */
  const composerOverlay = $("#composerOverlay");
  const elTitle = $("#cTitle");
  const elDek = $("#cDek");
  const elGenre = $("#cGenre");
  const elLang = $("#cLang");
  const elBody = $("#cBody");
  const elEditingId = $("#editingId");
  const imgDrop = $("#imgDrop");
  const imgInput = $("#imgInput");
  const imgPreview = $("#imgPreview");
  const imgPreviewEl = $("#imgPreviewEl");
  let currentImage = "";

  function applyLangFont() {
    const te = elLang.value === "te";
    [elTitle, elDek, elBody].forEach((el) => {
      el.style.fontFamily = te ? "var(--telugu)" : "";
    });
  }
  elLang.addEventListener("change", applyLangFont);

  function openComposer(editId) {
    if (editId) {
      const p = POSTS.find((x) => x.id === editId);
      if (p) {
        elEditingId.value = p.id;
        elTitle.value = p.title || "";
        elDek.value = p.dek || "";
        elGenre.value = p.genre || "Essay";
        elLang.value = p.lang || "en";
        elBody.value = p.body || "";
        setImage(p.image || "");
        $("#composerMode").textContent = "Edit post";
      }
    } else {
      elEditingId.value = "";
      elTitle.value = ""; elDek.value = ""; elBody.value = "";
      elGenre.value = "Essay"; elLang.value = "en";
      setImage("");
      $("#composerMode").textContent = "Write a new post";
    }
    applyLangFont();
    openOverlay(composerOverlay);
    composerOverlay.scrollTop = 0;
    setTimeout(() => elTitle.focus(), 250);
  }
  function closeComposer() { closeOverlay(composerOverlay); }

  function setImage(src) {
    currentImage = src || "";
    if (currentImage) {
      imgPreviewEl.src = currentImage;
      imgPreview.style.display = "block";
      imgDrop.style.display = "none";
    } else {
      imgPreview.style.display = "none";
      imgDrop.style.display = "block";
    }
  }

  /* image -> downscale + compress to keep storage small */
  function handleFile(file) {
    if (!file || !/^image\//.test(file.type)) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const max = 1400;
        let { width, height } = img;
        if (width > max || height > max) {
          const r = Math.min(max / width, max / height);
          width = Math.round(width * r);
          height = Math.round(height * r);
        }
        const c = document.createElement("canvas");
        c.width = width; c.height = height;
        c.getContext("2d").drawImage(img, 0, 0, width, height);
        setImage(c.toDataURL("image/jpeg", 0.82));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }
  imgDrop.addEventListener("click", () => imgInput.click());
  imgInput.addEventListener("change", (e) => handleFile(e.target.files[0]));
  imgDrop.addEventListener("dragover", (e) => { e.preventDefault(); imgDrop.style.borderColor = "var(--blue)"; });
  imgDrop.addEventListener("dragleave", () => { imgDrop.style.borderColor = ""; });
  imgDrop.addEventListener("drop", (e) => {
    e.preventDefault(); imgDrop.style.borderColor = "";
    handleFile(e.dataTransfer.files[0]);
  });
  $("#imgRemove").addEventListener("click", () => setImage(""));

  function publish() {
    const title = elTitle.value.trim();
    const body = elBody.value.trim();
    if (!title) { toast("Please add a title first."); elTitle.focus(); return; }
    if (!body) { toast("Write a little something before publishing."); elBody.focus(); return; }

    const editing = elEditingId.value;
    if (editing) {
      const p = POSTS.find((x) => x.id === editing);
      if (p) {
        Object.assign(p, {
          title, body,
          dek: elDek.value.trim(),
          genre: elGenre.value,
          lang: elLang.value,
          image: currentImage,
        });
      }
    } else {
      POSTS.push({
        id: uid(),
        title, body,
        dek: elDek.value.trim(),
        genre: elGenre.value,
        lang: elLang.value,
        image: currentImage,
        date: Date.now(),
      });
    }
    if (savePosts(POSTS)) {
      renderList();
      closeComposer();
      toast(editing ? "Post updated." : "Published! Your post is now live on the site.");
      setTimeout(() => {
        document.getElementById("writing").scrollIntoView({ behavior: "smooth" });
      }, 350);
    }
  }

  $("#publishBtn").addEventListener("click", publish);
  $("#openComposer").addEventListener("click", () => openComposer());
  $("#closeComposer").addEventListener("click", closeComposer);
  $("#cancelComposer").addEventListener("click", closeComposer);
  $("#closeReader").addEventListener("click", closeReader);

  /* ============================================================
     Overlay open/close + body scroll lock
     ============================================================ */
  function openOverlay(el) {
    el.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function closeOverlay(el) {
    el.classList.remove("open");
    if (!$(".overlay.open")) document.body.style.overflow = "";
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (composerOverlay.classList.contains("open")) closeComposer();
      else if (readerOverlay.classList.contains("open")) closeReader();
    }
  });

  /* ============================================================
     Toast
     ============================================================ */
  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
  }

  /* ============================================================
     Navigation: mobile menu, active link, reveal
     ============================================================ */
  const navLinks = $("#navLinks");
  $("#menuToggle").addEventListener("click", () => navLinks.classList.toggle("mobile-open"));
  $$("#navLinks a").forEach((a) => a.addEventListener("click", () => navLinks.classList.remove("mobile-open")));

  // active link on scroll
  const sections = ["featured", "writing", "books", "about", "contact"]
    .map((id) => document.getElementById(id)).filter(Boolean);
  const linkFor = {};
  $$("#navLinks a").forEach((a) => { linkFor[a.getAttribute("href").slice(1)] = a; });
  const navObserver = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) {
        $$("#navLinks a").forEach((a) => a.classList.remove("active"));
        const l = linkFor[en.target.id];
        if (l) l.classList.add("active");
      }
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach((s) => navObserver.observe(s));

  // reveal on scroll
  const revObserver = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add("in"); revObserver.unobserve(en.target); }
    });
  }, { threshold: 0.12 });
  $$(".reveal").forEach((el) => revObserver.observe(el));

  /* ---------- misc ---------- */
  $("#year").textContent = new Date().getFullYear();

  /* ---------- init ---------- */
  renderList();
})();
