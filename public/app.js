(() => {
  const $ = id => document.getElementById(id);
  const content = $("content"), toc = $("toc"), docsEl = $("docs"), side = $("side");
  let docs = [], index = [], current = null, io = null;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  /* ---------- C syntax highlighting (small, regex-based) ---------- */
  const KW = "auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while bool true false NULL uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t size_t";
  const kwRe = new RegExp("^(?:" + KW.split(" ").join("|") + ")$");
  const tokRe = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])+')|(^[ \t]*#[ \t]*\w+)|(\b0[xXbB][0-9a-fA-F]+[uUlL]*\b|\b\d+(?:\.\d+)?[fFuUlL]*\b)|(\b[A-Za-z_]\w*\b)/gm;
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  function highlight(src) {
    let out = "", last = 0, m;
    tokRe.lastIndex = 0;
    while ((m = tokRe.exec(src))) {
      out += esc(src.slice(last, m.index)); last = tokRe.lastIndex;
      const [t, com, str, pre, num, id] = m;
      if (com) out += `<span class="tc">${esc(t)}</span>`;
      else if (str) out += `<span class="ts">${esc(t)}</span>`;
      else if (pre) out += `<span class="tp">${esc(t)}</span>`;
      else if (num) out += `<span class="tn">${esc(t)}</span>`;
      else if (id && kwRe.test(t)) out += `<span class="tk">${esc(t)}</span>`;
      else out += esc(t);
    }
    return out + esc(src.slice(last));
  }
  function enhanceCode(root) {
    root.querySelectorAll("pre.code").forEach(pre => {
      const code = pre.firstElementChild, raw = code.textContent;
      code.innerHTML = highlight(raw);
      const b = document.createElement("button");
      b.className = "copy"; b.type = "button"; b.textContent = "Copy";
      b.onclick = async () => {
        try { await navigator.clipboard.writeText(raw); b.textContent = "Copied"; } catch (e) { b.textContent = "Press Ctrl+C"; }
        setTimeout(() => (b.textContent = "Copy"), 1400);
      };
      pre.appendChild(b);
    });
  }

  /* ---------- loading and routing ---------- */
  async function init() {
    ({ docs, index } = window.NOTES);
    docsEl.innerHTML = docs.map(d => `<a href="#${d.slug}" data-slug="${d.slug}"><strong>${d.title}</strong><span>${d.blurb}</span></a>`).join("");
    window.addEventListener("hashchange", route);
    route();
  }
  function parseHash() {
    const [slug, sec] = decodeURIComponent(location.hash.slice(1)).split("/");
    const ok = docs.find(d => d.slug === slug);
    return { slug: ok ? slug : (store.get("lastDoc") || docs[0].slug), sec: ok ? sec : null };
  }
  async function route() {
    const { slug, sec } = parseHash();
    closeMenu();
    const fresh = current !== slug;
    if (fresh) {
      const d = docs.find(x => x.slug === slug) || docs[0];
      content.innerHTML = '<p class="loading">Loading…</p>';
      content.innerHTML = window.NOTES.pages[d.slug];
      current = d.slug; store.set("lastDoc", current);
      document.title = `${d.title} · C & Embedded C notes`;
      docsEl.querySelectorAll("a").forEach(a => a.dataset.slug === current ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
      enhanceCode(content); buildToc(d); reveal();
      content.classList.remove("enter"); void content.offsetWidth; content.classList.add("enter");
      const saved = +store.get("pos:" + current) || 0;
      window.scrollTo({ top: !sec ? saved : 0, behavior: "instant" });
    }
    if (sec) { const el = document.getElementById(sec); if (el) { el.classList.add("in"); el.scrollIntoView({ behavior: fresh ? "instant" : "smooth", block: "start" }); } }
    content.focus({ preventScroll: true });
  }

  /* ---------- gentle reveal for code, tables and callouts ---------- */
  let rio = null;
  function reveal() {
    if (rio) rio.disconnect();
    const els = [...content.querySelectorAll("pre.code:not(.mini), .callout, .tablewrap")].filter(e => !e.parentElement.closest(".callout, .tablewrap"));
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    rio = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); rio.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px" });
    els.forEach(e => { if (e.getBoundingClientRect().top > innerHeight * 0.9) { e.classList.add("rv"); rio.observe(e); } });
  }

  /* ---------- table of contents ---------- */
  function buildToc(d) {
    const heads = [...content.querySelectorAll("h1[id],h2[id]")];
    toc.innerHTML = heads.map(h => `<a class="${h.tagName.toLowerCase()}" href="#${current}/${h.id}" data-id="${h.id}">${h.textContent}</a>`).join("")
      + `<a class="dl" href="${d.docx}" download>Download the Word file</a>`;
    if (io) io.disconnect();
    io = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) mark(e.target.id); });
    }, { rootMargin: "-70px 0px -75% 0px" });
    heads.forEach(h => io.observe(h));
  }
  function mark(id) {
    toc.querySelectorAll("a.on").forEach(a => a.classList.remove("on"));
    const a = toc.querySelector(`a[data-id="${CSS.escape(id)}"]`);
    if (a) { a.classList.add("on"); const r = a.getBoundingClientRect(), s = side.getBoundingClientRect();
      if (r.top < s.top + 60 || r.bottom > s.bottom - 20) side.scrollTop += r.top - s.top - s.height / 3; }
  }

  /* ---------- reading progress and position ---------- */
  let tick;
  addEventListener("scroll", () => {
    const h = document.documentElement, max = h.scrollHeight - innerHeight;
    $("progress").style.transform = `scaleX(${max > 0 ? scrollY / max : 0})`;
    clearTimeout(tick); tick = setTimeout(() => current && store.set("pos:" + current, Math.round(scrollY)), 300);
  }, { passive: true });

  /* ---------- search ---------- */
  const qEl = $("q"), resEl = $("results");
  const hl = (s, words) => esc(s).replace(new RegExp("(" + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi"), "<mark>$1</mark>");
  qEl.addEventListener("input", () => {
    const words = qEl.value.toLowerCase().split(/\s+/).filter(w => w.length > 1);
    if (!words.length) { resEl.hidden = true; return; }
    const hits = [];
    for (const s of index) {
      const t = s.title.toLowerCase(), body = s.text.toLowerCase();
      if (!words.every(w => t.includes(w) || body.includes(w))) continue;
      const score = words.reduce((n, w) => n + (t.includes(w) ? 5 : 0) + (body.split(w).length - 1), 0);
      const at = Math.max(0, body.indexOf(words[0]) - 50);
      hits.push({ s, score, snip: s.text.slice(at, at + 140) });
    }
    hits.sort((a, b) => b.score - a.score);
    const name = slug => docs.find(d => d.slug === slug).title;
    resEl.innerHTML = hits.length
      ? hits.slice(0, 20).map(h => `<a href="#${h.s.doc}/${h.s.id}"><b>${hl(h.s.title, words)}</b> <small>${name(h.s.doc)}</small><br>${hl(h.snip, words)}…</a>`).join("")
      : "<p>No matches. Try a shorter word, like “pointer” or “volatile”.</p>";
    resEl.hidden = false;
  });
  resEl.addEventListener("click", e => { if (e.target.closest("a")) { resEl.hidden = true; qEl.blur(); } });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) resEl.hidden = true; });
  addEventListener("keydown", e => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); qEl.focus(); }
    if (e.key === "Escape") { resEl.hidden = true; closeMenu(); qEl.blur(); }
  });

  /* ---------- theme and mobile menu ---------- */
  $("themeBtn").onclick = () => {
    const r = document.documentElement, dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.classList.add("tx"); setTimeout(() => r.classList.remove("tx"), 600);
    r.dataset.theme = dark ? "light" : "dark"; store.set("theme", r.dataset.theme);
  };
  const scrim = $("scrim"), menuBtn = $("menuBtn");
  function closeMenu() { side.classList.remove("open"); scrim.hidden = true; menuBtn.setAttribute("aria-expanded", "false"); }
  menuBtn.onclick = () => { const o = side.classList.toggle("open"); scrim.hidden = !o; menuBtn.setAttribute("aria-expanded", o); };
  scrim.onclick = closeMenu;

  if (window.NOTES) init(); else content.innerHTML = "<p>The file data.js is missing. Upload the whole public folder, including data.js, and reload.</p>";
})();
