// Portfolix Studio — orchestrates the static landing site.
// Loads output/data.json (produced by `python generate.py`), lets the user pick
// document types, toggle AI copy, render everything into isolated
// iframes, preview, and live-edit the HTML/CSS of any document.

import { startBackground } from "./background.js";
import { DOC_TYPES } from "./docs.js";

const $ = (sel) => document.querySelector(sel);
const state = {
  data: null,
  selected: new Set(["portfolio"]),
  docs: new Map(), // id -> { def, title, html, css, dirty }
  editing: null,   // id currently in the editor
  beautify: false, // apply the AI style pack (if present)
};

// ---- Theme ---------------------------------------------------------------

function initTheme() {
  const root = document.documentElement;
  const saved = localStorage.getItem("portfolix-theme");
  if (saved) root.setAttribute("data-theme", saved);
  $("#themeToggle").addEventListener("click", () => {
    const cur = root.getAttribute("data-theme")
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("portfolix-theme", next);
    // Re-render open docs so their inks match the new theme.
    rerenderAll();
  });
}

// ---- Data load -----------------------------------------------------------

async function loadData() {
  try {
    const res = await fetch("../output/data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    state.data = await res.json();
  } catch {
    // Fallback: allow the site to be hosted with data.json beside it.
    try {
      const res2 = await fetch("./data.json", { cache: "no-store" });
      if (!res2.ok) throw new Error(res2.status);
      state.data = await res2.json();
    } catch {
      $("#loadedFor").innerHTML =
        `⚠️ Could not load <code>data.json</code>. Run <code>python generate.py --username YOU</code> first, ` +
        `then reload. (Serve this folder over http, not file://.)`;
      return false;
    }
  }
  const p = state.data.profile;
  $("#loadedFor").innerHTML = `Loaded <strong>${escapeHtml(p.name)}</strong> — ` +
    `${state.data.repos.length} repos · ${state.data.total_stars} stars` +
    (hasAI() ? " · ✨ AI copy available" : " · (no AI copy — run with GEMINI_API_KEY for enhanced text)");
  return true;
}

function hasAI() {
  const ai = state.data && state.data.ai;
  return !!(ai && (ai.narrative || ai.headline || ai.cover_letter || (ai.brag_sheet && ai.brag_sheet.length)));
}

// ---- Controls ------------------------------------------------------------

function buildControls() {
  const picker = $("#docPicker");
  picker.innerHTML = DOC_TYPES.map((d) => `
    <div class="doc-chip ${state.selected.has(d.id) ? "on" : ""}" data-id="${d.id}" role="checkbox" tabindex="0"
         aria-checked="${state.selected.has(d.id)}">
      <span class="box"></span>
      <span><span class="dc-title">${d.name}</span><br><span class="dc-desc">${d.desc}</span></span>
    </div>`).join("");

  picker.querySelectorAll(".doc-chip").forEach((chip) => {
    const toggle = () => {
      const id = chip.dataset.id;
      if (state.selected.has(id)) state.selected.delete(id);
      else state.selected.add(id);
      chip.classList.toggle("on");
      chip.setAttribute("aria-checked", state.selected.has(id));
    };
    chip.addEventListener("click", toggle);
    chip.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
    });
  });

  const aiToggle = $("#aiToggle");
  aiToggle.checked = hasAI();
  aiToggle.disabled = !hasAI();
  $("#aiState").textContent = hasAI() ? "" : "(unavailable)";

  const bToggle = $("#beautifyToggle");
  bToggle.disabled = !hasStylePack();
  $("#beautifyState").textContent = hasStylePack()
    ? (stylePack().name ? `(${stylePack().name})` : "")
    : "(run with GEMINI_API_KEY)";
  bToggle.addEventListener("change", () => {
    state.beautify = bToggle.checked;
    // Re-skin every open doc (including hand-edited ones — it's just an overlay).
    state.docs.forEach((_, id) => writeFrame(id));
  });

  $("#generateBtn").addEventListener("click", generate);
}

// ---- Generation ----------------------------------------------------------

function opts() {
  return { useAI: $("#aiToggle").checked && hasAI() };
}

function generate() {
  if (!state.selected.size) { alert("Pick at least one document."); return; }
  const stage = $("#stage");
  stage.innerHTML = "";
  state.docs.clear();

  DOC_TYPES.filter((d) => state.selected.has(d.id)).forEach((def) => {
    const rendered = def.render(state.data, opts(), document.documentElement);
    state.docs.set(def.id, { def, ...rendered, dirty: false });
    stage.appendChild(makeDocCard(def.id));
  });
  if (!state.docs.size) stage.innerHTML = `<div class="empty">Nothing selected.</div>`;
}

function rerenderAll() {
  // Re-render only docs that haven't been hand-edited, so we don't clobber edits.
  state.docs.forEach((doc, id) => {
    if (doc.dirty) return;
    const rendered = doc.def.render(state.data, opts(), document.documentElement);
    Object.assign(doc, rendered);
    writeFrame(id);
  });
}

// The AI style pack (from data.ai.beautified_css), if present.
function stylePack() {
  const pack = state.data && state.data.ai && state.data.ai.beautified_css;
  return pack && Object.keys(pack).length ? pack : null;
}
function hasStylePack() { return !!stylePack(); }

// Curated Google Fonts the style pack may request. Family name → { stack, spec }
// where `spec` is the Google Fonts URL family+weights segment. Restricting to a
// known list means the AI can't inject arbitrary @import URLs.
const FONTS = {
  // Heading sans
  "Poppins": { stack: `'Poppins', sans-serif`, spec: "Poppins:wght@500;600;700;800" },
  "Montserrat": { stack: `'Montserrat', sans-serif`, spec: "Montserrat:wght@500;600;700;800" },
  "Sora": { stack: `'Sora', sans-serif`, spec: "Sora:wght@500;600;700;800" },
  "Space Grotesk": { stack: `'Space Grotesk', sans-serif`, spec: "Space+Grotesk:wght@500;600;700" },
  "Outfit": { stack: `'Outfit', sans-serif`, spec: "Outfit:wght@500;600;700;800" },
  "Archivo": { stack: `'Archivo', sans-serif`, spec: "Archivo:wght@500;600;700;800" },
  // Serif
  "Playfair Display": { stack: `'Playfair Display', Georgia, serif`, spec: "Playfair+Display:wght@600;700;800" },
  "Fraunces": { stack: `'Fraunces', Georgia, serif`, spec: "Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700" },
  "Cormorant Garamond": { stack: `'Cormorant Garamond', Georgia, serif`, spec: "Cormorant+Garamond:wght@600;700" },
  "Lora": { stack: `'Lora', Georgia, serif`, spec: "Lora:wght@500;600;700" },
  // Script
  "Dancing Script": { stack: `'Dancing Script', cursive`, spec: "Dancing+Script:wght@500;600;700" },
  "Great Vibes": { stack: `'Great Vibes', cursive`, spec: "Great+Vibes" },
  "Sacramento": { stack: `'Sacramento', cursive`, spec: "Sacramento" },
  // Body
  "Inter": { stack: `'Inter', system-ui, sans-serif`, spec: "Inter:wght@400;500;600;700" },
  "Work Sans": { stack: `'Work Sans', system-ui, sans-serif`, spec: "Work+Sans:wght@400;500;600;700" },
  "DM Sans": { stack: `'DM Sans', system-ui, sans-serif`, spec: "DM+Sans:wght@400;500;600;700" },
  "Nunito Sans": { stack: `'Nunito Sans', system-ui, sans-serif`, spec: "Nunito+Sans:wght@400;600;700" },
};

// Build a Google Fonts @import for whichever pack families are in the allow-list.
function fontImportFor(p) {
  const specs = [];
  for (const key of ["heading_family", "body_family", "signature_family"]) {
    const f = FONTS[p[key]];
    if (f && !specs.includes(f.spec)) specs.push(f.spec);
  }
  if (!specs.length) return "";
  return `@import url('https://fonts.googleapis.com/css2?${specs.map((s) => "family=" + s).join("&")}&display=swap');`;
}

// Turn the style pack into a rich CSS overlay: real font pairing, gradient accents,
// section styling, colored rules. Every field is validated; the rules never touch
// layout geometry, so a wild pack can't break a document — it only re-skins it.
function stylePackCss() {
  const p = stylePack();
  if (!p) return "";
  const rules = [];
  const imp = fontImportFor(p);
  if (imp) rules.push(imp); // @import must come first in the stylesheet

  if (isHex(p.accent_light)) rules.push(`:root,:root[data-theme="light"]{--accent:${p.accent_light}}`);
  if (isHex(p.accent_dark)) {
    rules.push(`@media(prefers-color-scheme:dark){:root{--accent:${p.accent_dark}}}`);
    rules.push(`:root[data-theme="dark"]{--accent:${p.accent_dark}}`);
  }

  const body = FONTS[p.body_family];
  if (body) rules.push(`body{font-family:${body.stack}}`);

  // Heading pairing: family, weight, tracking.
  const head = FONTS[p.heading_family];
  const hParts = [];
  if (head) hParts.push(`font-family:${head.stack}`);
  const hw = parseInt(p.heading_weight, 10);
  if (hw >= 400 && hw <= 900) hParts.push(`font-weight:${hw}`);
  if (typeof p.letter_spacing === "string" && /^-?[\d.]{1,6}em$/.test(p.letter_spacing)) {
    hParts.push(`letter-spacing:${p.letter_spacing}`);
  }
  if (hParts.length) rules.push(`h1,h2,h3,.dc-title{${hParts.join(";")}}`);

  // Gradient identity: gradient-filled display headings & hero numbers, a soft
  // top wash, gradient link pills on hover, accented section rules & bars.
  const g = p.gradient;
  if (g && isHex(g.from) && isHex(g.to)) {
    const angle = (typeof g.angle === "string" && /^\d{1,3}deg$/.test(g.angle)) ? g.angle : "135deg";
    const grad = `linear-gradient(${angle},${g.from},${g.to})`;
    rules.push(
      `h1,.stat .num,.glance b,.headline{background-image:${grad};-webkit-background-clip:text;` +
      `background-clip:text;color:transparent;-webkit-text-fill-color:transparent}`
    );
    // h2 section headers get a gradient underline accent (keeps them readable).
    rules.push(`h2{position:relative;padding-bottom:6px}`);
    rules.push(`h2::after{content:"";position:absolute;left:0;bottom:0;width:44px;height:3px;border-radius:3px;background-image:${grad}}`);
    rules.push(`body{background-image:linear-gradient(180deg,color-mix(in srgb,${g.from} 10%,transparent),transparent 320px)}`);
    rules.push(`.links a:hover{background-image:${grad};color:#fff;border-color:transparent}`);
    rules.push(`.avatar{border-color:${g.from};box-shadow:0 0 0 4px color-mix(in srgb,${g.from} 22%,transparent)}`);
    rules.push(`.langbar,.bar{box-shadow:0 0 0 1px color-mix(in srgb,${g.to} 30%,transparent)}`);
    rules.push(`.tag{border-color:color-mix(in srgb,${g.from} 40%,transparent)}`);
    rules.push(`.card:hover{border-color:${g.from}}`);
    // Cover-letter signature gets the script font + accent.
    const sig = FONTS[p.signature_family];
    if (sig) rules.push(`.signature{font-family:${sig.stack};font-size:2.1rem;line-height:1;color:${g.from}}`);
  } else {
    const sig = FONTS[p.signature_family];
    if (sig) rules.push(`.signature{font-family:${sig.stack};font-size:2.1rem;line-height:1}`);
  }

  if (typeof p.radius === "string" && /^[\d.]{1,5}(px|rem|em)$/.test(p.radius)) {
    rules.push(`.card,.stat,.matrix,.langbar,.links a,.tag,.proj{border-radius:${p.radius} !important}`);
  }
  return rules.join("\n");
}
function isHex(v) { return typeof v === "string" && /^#[0-9a-fA-F]{3,8}$/.test(v); }

// Compose a full standalone HTML document from a doc's html + css.
function composeDoc(doc) {
  const themeAttr = document.documentElement.getAttribute("data-theme");
  const beautify = state.beautify ? `<style>${stylePackCss()}</style>` : "";
  return `<!doctype html><html${themeAttr ? ` data-theme="${themeAttr}"` : ""}><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>${doc.css}</style>${beautify}</head><body>${doc.html}</body></html>`;
}

function makeDocCard(id) {
  const doc = state.docs.get(id);
  const card = document.createElement("div");
  card.className = "doc";
  card.dataset.id = id;
  card.innerHTML = `
    <div class="doc-bar">
      <span class="doc-name">${escapeHtml(doc.title)}</span>
      <span class="spacer"></span>
      <button class="btn tiny" data-act="edit">✎ Edit</button>
      <button class="btn tiny" data-act="download">⬇ Download HTML</button>
    </div>
    <div class="doc-body"><iframe class="doc-frame" data-id="${id}" title="${escapeHtml(doc.title)}"></iframe></div>`;
  card.querySelector('[data-act="edit"]').addEventListener("click", () => openEditor(id));
  card.querySelector('[data-act="download"]').addEventListener("click", () => downloadDoc(id));

  // Write the frame after it's in the DOM.
  requestAnimationFrame(() => writeFrame(id));
  return card;
}

function writeFrame(id) {
  const frame = document.querySelector(`iframe.doc-frame[data-id="${id}"]`);
  if (!frame) return;
  const doc = state.docs.get(id);
  frame.srcdoc = composeDoc(doc);
  frame.onload = () => sizeFrame(frame);
}

function sizeFrame(frame) {
  try {
    const h = frame.contentDocument.body.scrollHeight;
    frame.style.height = Math.max(h + 8, 200) + "px";
  } catch { frame.style.height = "600px"; }
}

function downloadDoc(id) {
  const doc = state.docs.get(id);
  const blob = new Blob([composeDoc(doc)], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${state.data.profile.login}_${id}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- Live editor sidebar --------------------------------------------------

function initEditor() {
  $("#editFab").addEventListener("click", () => {
    if (state.editing) toggleEditor();
    else if (state.docs.size) openEditor(state.docs.keys().next().value);
    else alert("Generate a document first, then edit it.");
  });
  $("#editClose").addEventListener("click", closeEditor);
  $("#editApply").addEventListener("click", applyEdit);
  $("#editReset").addEventListener("click", resetEdit);

  document.querySelectorAll(".editor-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".editor-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const isHtml = tab.dataset.tab === "html";
      $("#editHtml").hidden = !isHtml;
      $("#editCss").hidden = isHtml;
    });
  });

  initEditorResize();
}

function openEditor(id) {
  state.editing = id;
  const doc = state.docs.get(id);
  $("#editorTarget").textContent = `Editing: ${doc.title}`;
  $("#editHtml").value = doc.html;
  $("#editCss").value = doc.css;
  $("#editor").classList.add("open");
  $("#editor").setAttribute("aria-hidden", "false");
}
function toggleEditor() { $("#editor").classList.toggle("open"); }
function closeEditor() {
  $("#editor").classList.remove("open");
  $("#editor").setAttribute("aria-hidden", "true");
}
function applyEdit() {
  if (!state.editing) return;
  const doc = state.docs.get(state.editing);
  doc.html = $("#editHtml").value;
  doc.css = $("#editCss").value;
  doc.dirty = true; // protect from theme re-renders
  writeFrame(state.editing);
}
function resetEdit() {
  if (!state.editing) return;
  const doc = state.docs.get(state.editing);
  const rendered = doc.def.render(state.data, opts(), document.documentElement);
  Object.assign(doc, rendered, { dirty: false });
  $("#editHtml").value = doc.html;
  $("#editCss").value = doc.css;
  writeFrame(state.editing);
}

function initEditorResize() {
  const editor = $("#editor");
  const grip = $("#editorGrip");
  let dragging = false;
  grip.addEventListener("pointerdown", (e) => {
    dragging = true; grip.setPointerCapture(e.pointerId); e.preventDefault();
  });
  window.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const w = Math.min(Math.max(window.innerWidth - e.clientX, 320), window.innerWidth * 0.92);
    editor.style.width = w + "px";
  });
  window.addEventListener("pointerup", () => { dragging = false; });
}

// ---- Utils ---------------------------------------------------------------

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---- Boot ----------------------------------------------------------------

async function main() {
  try { startBackground($("#bg")); } catch (e) { console.warn("bg failed", e); }
  initTheme();
  initEditor();
  const ok = await loadData();
  if (!ok) return;
  buildControls();
  generate(); // render the default selection immediately
}

main();
