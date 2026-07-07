// In-browser document renderers. Each returns { title, html, css }.
// `html` is the <body> content; `css` is the document stylesheet. They are
// composed into a full self-contained document (see app.js buildDoc) that is
// injected into an isolated iframe, so a doc can be edited/printed on its own.

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
));

// Language color chips reused by cards.
const LANG_COLORS = {
  Python: "#3572A5", JavaScript: "#f1e05a", TypeScript: "#3178c6", HTML: "#e34c26",
  CSS: "#563d7c", Java: "#b07219", "C++": "#f34b7d", C: "#555555", "C#": "#178600",
  Go: "#00ADD8", Rust: "#dea584", Ruby: "#701516", PHP: "#4F5D95", Swift: "#F05138",
  Kotlin: "#A97BFF", Shell: "#89e051", Dart: "#00B4AB", "Jupyter Notebook": "#DA5B0B",
};
const langColor = (n) => LANG_COLORS[n] || "#8b949e";

// Shared theme-aware base CSS every document inherits.
const LIGHT_VARS = `--surface:#fcfcfb; --surface-2:#f4f4f2; --fg:#111; --fg-2:#444; --muted:#888;
  --border:rgba(0,0,0,.09); --border-solid:#e5e5e2; --accent:#2a78d6;`;
const DARK_VARS = `--surface:#1a1a19; --surface-2:#242423; --fg:#f4f4f4; --fg-2:#c9c9c2;
  --muted:#8f8f88; --border:rgba(255,255,255,.10); --border-solid:#333; --accent:#3987e5;`;

const BASE_CSS = `
:root { ${LIGHT_VARS} }
@media (prefers-color-scheme: dark) { :root { ${DARK_VARS} } }
/* The Studio stamps data-theme on <html>; those overrides must win in both directions. */
:root[data-theme="light"] { ${LIGHT_VARS} }
:root[data-theme="dark"] { ${DARK_VARS} }
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--fg);
  font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 32px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
h1,h2,h3 { letter-spacing: -.02em; }
.wrap { max-width: 860px; margin: 0 auto; }
/* Signature default (a refined italic serif); beautify swaps in a real script font. */
.signature { font-family: "Snell Roundhand", "Segoe Script", "Brush Script MT", cursive;
  font-size: 1.9rem; line-height: 1; color: var(--accent); }
`;

function bio(d, useAI) {
  if (useAI && d.ai && d.ai.narrative) return d.ai.narrative;
  return d.profile.bio || "";
}
function repoSummary(r, useAI) {
  if (useAI && r.ai_summary) return r.ai_summary;
  return r.description || "No description provided.";
}

// Label a profile link by what it points at (LinkedIn, Twitter/X, a clean domain,
// or "Website"). GitHub stores whatever a user puts in their profile "blog" field
// here — often a LinkedIn URL — so a bare "Website" would be misleading.
function linkLabel(url) {
  try {
    const host = new URL(url.startsWith("http") ? url : "https://" + url).hostname.replace(/^www\./, "");
    if (host.includes("linkedin.")) return "LinkedIn";
    if (host === "twitter.com" || host === "x.com") return "Twitter/X";
    if (host.includes("github.")) return "GitHub";
    return host || "Website";
  } catch {
    return "Website";
  }
}

// ---- Portfolio (responsive single-page site) ------------------------------

export function renderPortfolio(d, { useAI }, root) {
  const p = d.profile;
  const stats = [
    ["Repos", p.public_repos], ["Stars", d.total_stars],
    ["Forks", d.total_forks], ["Followers", p.followers],
  ];
  if (d.contributions != null) stats.push(["Contributions/yr", d.contributions]);

  const langs = d.languages.slice(0, 8);
  const langBar = langs.map((l) =>
    `<span style="width:${l.pct}%;background:${langColor(l.name)}" title="${esc(l.name)} ${l.pct}%"></span>`
  ).join("");
  // The language legend list (JavaScript 66.7%, HTML 15.5%, …).
  const langLegend = langs.map((l) =>
    `<span class="lang-item"><span class="ldot" style="background:${langColor(l.name)}"></span>${esc(l.name)}<span class="lpct">${l.pct}%</span></span>`
  ).join("");

  const cards = d.pinned.map((r) => `
    <div class="card">
      <h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a></h3>
      <p>${esc(repoSummary(r, useAI))}</p>
      ${r.topics.length ? `<div class="tags">${r.topics.slice(0, 5).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
      <div class="foot">
        ${r.language ? `<span class="lang"><span class="cdot" style="background:${langColor(r.language)}"></span>${esc(r.language)}</span>` : ""}
        <span>★ ${r.stars}</span>
        ${r.homepage ? `<a class="live" href="${esc(r.homepage)}" target="_blank" rel="noopener">Live ↗</a>` : ""}
      </div>
    </div>`).join("");

  const genDate = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });

  const html = `<div class="wrap">
    <header class="p-head">
      ${p.avatar_url ? `<img class="avatar" src="${esc(p.avatar_url)}" alt="${esc(p.name)}">` : ""}
      <h1>${esc(p.name)}</h1>
      ${bio(d, useAI) ? `<p class="bio">${esc(bio(d, useAI))}</p>` : ""}
      <div class="meta">
        ${p.company ? `<span>🏢 ${esc(p.company)}</span>` : ""}
        ${p.location ? `<span>📍 ${esc(p.location)}</span>` : ""}
      </div>
      <div class="links"><a href="${esc(p.html_url)}" target="_blank" rel="noopener">GitHub</a>
      ${p.blog ? `<a href="${esc(p.blog)}" target="_blank" rel="noopener">${esc(linkLabel(p.blog))}</a>` : ""}</div>
    </header>
    <div class="stats">${stats.map(([l, v]) => `<div class="stat"><div class="num">${v}</div><div class="lbl">${l}</div></div>`).join("")}</div>
    ${langs.length ? `<section><h2>Languages</h2><div class="langbar">${langBar}</div><div class="langlegend">${langLegend}</div></section>` : ""}
    ${d.pinned.length ? `<section><h2>Featured Projects</h2><div class="grid">${cards}</div></section>` : ""}
    <footer class="p-foot">Generated by <strong>Portfolix</strong> on ${genDate} · Data from GitHub</footer>
  </div>`;

  const css = BASE_CSS + `
    .p-head { text-align: center; padding: 20px 0 8px; }
    .avatar { width: 110px; height: 110px; border-radius: 50%; border: 3px solid var(--border-solid); object-fit: cover; }
    h1 { font-size: 2rem; margin: 14px 0 2px; }
    .bio { color: var(--fg-2); max-width: 620px; margin: 8px auto 0; }
    .meta { color: var(--muted); font-size: .9rem; margin-top: 12px; }
    .meta span { margin: 0 8px; white-space: nowrap; }
    .links { margin-top: 14px; }
    .links a { display: inline-block; margin: 4px; padding: 7px 15px; border: 1px solid var(--border-solid);
      border-radius: 999px; color: var(--fg); background: var(--surface-2); font-size: .85rem; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit,minmax(110px,1fr)); gap: 10px; margin: 28px 0; }
    .stat { background: var(--surface-2); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: center; }
    .stat .num { font-size: 1.6rem; font-weight: 700; }
    .stat .lbl { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
    section { margin: 36px 0; }
    h2 { font-size: 1.2rem; margin: 0 0 16px; }
    .langbar { display: flex; height: 12px; border-radius: 999px; overflow: hidden; border: 1px solid var(--border-solid); }
    .langbar > span { display: block; height: 100%; }
    .langlegend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 14px; font-size: .9rem; }
    .lang-item { white-space: nowrap; }
    .ldot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
    .lpct { color: var(--muted); margin-left: 5px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(260px,1fr)); gap: 14px; }
    .card { background: var(--surface-2); border: 1px solid var(--border); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; }
    .card h3 { margin: 0 0 6px; font-size: 1.05rem; }
    .card p { margin: 0 0 12px; color: var(--fg-2); font-size: .9rem; flex: 1; }
    .tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
    .tag { font-size: .68rem; padding: 2px 8px; border-radius: 999px; background: var(--surface); color: var(--accent); border: 1px solid var(--border); }
    .foot { display: flex; align-items: center; gap: 14px; font-size: .8rem; color: var(--muted); }
    .cdot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; }
    .live { margin-left: auto; }
    .p-foot { text-align: center; color: var(--muted); font-size: .82rem; padding: 30px 0 10px; margin-top: 24px; border-top: 1px solid var(--border); }`;

  return { title: "Portfolio", html, css, printable: false };
}

// ---- Technical CV (print-optimized, one page) -----------------------------

export function renderCV(d, { useAI }, root) {
  const p = d.profile;
  const langs = d.languages.slice(0, 10).map((l) => `${esc(l.name)} (${l.pct}%)`).join(" · ");
  const projects = d.pinned.map((r) => `
    <div class="proj">
      <div class="proj-top"><span class="proj-name">${esc(r.name)}</span><span class="proj-meta">★ ${r.stars} · ⑂ ${r.forks}</span></div>
      <div class="proj-desc">${esc(repoSummary(r, useAI))}</div>
      <div class="proj-tech">${r.language ? esc(r.language) : ""}${r.topics.length ? " · " + esc(r.topics.slice(0, 5).join(", ")) : ""} · ${esc(r.url)}</div>
    </div>`).join("");

  const stats = [["Public Repos", p.public_repos], ["Total Stars", d.total_stars],
    ["Total Forks", d.total_forks], ["Followers", p.followers]];
  if (d.contributions != null) stats.push(["Contribs/yr", d.contributions]);

  const html = `<div class="cv">
    <header>
      <h1>${esc(p.name)}</h1>
      <div class="contact">
        ${p.location ? `<span>📍 ${esc(p.location)}</span>` : ""}
        ${p.company ? `<span>🏢 ${esc(p.company)}</span>` : ""}
        <span>🔗 ${esc(p.html_url)}</span>${p.blog ? `<span>🌐 ${esc(p.blog)}</span>` : ""}
      </div>
      ${bio(d, useAI) ? `<p class="summary">${esc(bio(d, useAI))}</p>` : ""}
    </header>
    <h2>At a Glance</h2>
    <div class="glance">${stats.map(([l, v]) => `<div><b>${v}</b><span>${l}</span></div>`).join("")}</div>
    ${langs ? `<h2>Technical Skills</h2><p class="skills">${langs}</p>` : ""}
    <h2>Featured Projects</h2>${projects}
  </div>`;

  const css = BASE_CSS + `
    body { padding: 0; background: #fff; color: #1a1a1a; }
    .cv { max-width: 800px; margin: 0 auto; padding: 40px; }
    header { border-bottom: 2px solid #1a1a1a; padding-bottom: 10px; }
    h1 { font-size: 1.9rem; margin: 0 0 3px; }
    .contact { font-size: .8rem; color: #444; }
    .contact span { margin-right: 12px; }
    .summary { font-size: .92rem; color: #333; margin: 8px 0 0; }
    h2 { font-size: .95rem; text-transform: uppercase; letter-spacing: .05em; color: #0b5cad;
      border-bottom: 1px solid #ccc; padding-bottom: 3px; margin: 20px 0 10px; }
    .glance { display: flex; gap: 0; }
    .glance div { flex: 1; text-align: center; }
    .glance b { display: block; font-size: 1.3rem; }
    .glance span { font-size: .68rem; text-transform: uppercase; color: #666; }
    .skills { font-size: .88rem; color: #333; }
    .proj { margin-bottom: 11px; page-break-inside: avoid; }
    .proj-top { display: flex; justify-content: space-between; align-items: baseline; }
    .proj-name { font-weight: 700; }
    .proj-meta { font-size: .78rem; color: #666; }
    .proj-desc { font-size: .9rem; color: #333; }
    .proj-tech { font-size: .72rem; color: #777; }
    @media print { @page { size: A4; margin: 16mm; } body { padding: 0; } .cv { padding: 0; } }`;

  return { title: "Technical CV", html, css, printable: true };
}

// ---- Cover letter ---------------------------------------------------------

export function renderCoverLetter(d, { useAI }, root) {
  const p = d.profile;
  const bodyText = (useAI && d.ai && d.ai.cover_letter)
    ? d.ai.cover_letter
    : "Enable AI enhancement and regenerate to draft a cover letter body from your GitHub projects, or write your own here.";
  const paras = bodyText.split(/\n\s*\n/).map((para) => `<p>${esc(para.trim())}</p>`).join("");

  const html = `<div class="letter">
    <header>
      <h1>${esc(p.name)}</h1>
      <div class="meta">${p.location ? esc(p.location) + " · " : ""}${esc(p.html_url)}${p.blog ? " · " + esc(p.blog) : ""}</div>
    </header>
    <p class="date">${new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</p>
    <p>Dear [Company] Hiring Team,</p>
    ${paras}
    <div class="signoff">Sincerely,<div class="signature">${esc(p.name)}</div><div class="signprint">${esc(p.name)}</div></div>
  </div>`;

  const css = BASE_CSS + `
    body { padding: 0; background: #fff; color: #1a1a1a; }
    .letter { max-width: 720px; margin: 0 auto; padding: 48px; font-size: 1rem; line-height: 1.7; }
    header { margin-bottom: 20px; }
    h1 { font-size: 1.5rem; margin: 0; }
    .meta { color: #666; font-size: .82rem; }
    .date { color: #666; }
    .signoff { margin-top: 30px; }
    /* .signature is the script-font name; it only styles up once beautify is on.
       Until then it renders as plain text, so hide the plain fallback duplicate. */
    .signature { margin-top: 6px; }
    .signprint { display: none; }
    p { margin: 0 0 14px; }
    @media print { @page { size: A4; margin: 20mm; } .letter { padding: 0; } }`;

  return { title: "Cover Letter", html, css, printable: true };
}

// ---- Skills / brag sheet --------------------------------------------------

export function renderBragSheet(d, { useAI }, root) {
  const p = d.profile;
  const bullets = (useAI && d.ai && d.ai.brag_sheet && d.ai.brag_sheet.length)
    ? d.ai.brag_sheet
    : [
        `Maintains ${p.public_repos} public repositories on GitHub.`,
        `Accumulated ${d.total_stars} stars and ${d.total_forks} forks across projects.`,
        d.contributions != null ? `Logged ${d.contributions} contributions in the last year.` : null,
        d.languages.length ? `Works across ${d.languages.length} languages, led by ${d.languages[0].name}.` : null,
      ].filter(Boolean);

  const skillMatrix = d.languages.slice(0, 10).map((l) => {
    const level = l.pct >= 30 ? "Expert" : l.pct >= 10 ? "Proficient" : "Familiar";
    return `<tr><td>${esc(l.name)}</td><td><span class="bar"><span style="width:${Math.min(100, l.pct)}%"></span></span></td><td class="lvl">${level}</td></tr>`;
  }).join("");

  const html = `<div class="wrap">
    <header><h1>${esc(p.name)} — Skills &amp; Achievements</h1>
      <p class="sub">A quantified brag sheet from GitHub activity. Use in performance reviews or to seed a résumé.</p></header>
    <section><h2>Achievements</h2><ul class="brag">${bullets.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></section>
    <section><h2>Skill Matrix</h2><table class="matrix"><tbody>${skillMatrix}</tbody></table></section>
  </div>`;

  const css = BASE_CSS + `
    header h1 { font-size: 1.6rem; margin: 0 0 4px; }
    .sub { color: var(--fg-2); margin: 0; }
    section { margin: 28px 0; }
    h2 { font-size: 1.05rem; border-bottom: 1px solid var(--border-solid); padding-bottom: 4px; }
    .brag { padding-left: 20px; }
    .brag li { margin-bottom: 8px; }
    .matrix { width: 100%; border-collapse: collapse; font-size: .9rem; }
    .matrix td { padding: 8px 6px; border-bottom: 1px solid var(--border); }
    .matrix td:first-child { font-weight: 600; width: 130px; }
    .bar { display: block; height: 8px; background: var(--border-solid); border-radius: 999px; overflow: hidden; }
    .bar span { display: block; height: 100%; background: var(--accent); border-radius: 999px; }
    .lvl { color: var(--muted); width: 90px; text-align: right; }
    @media print { @page { size: A4; margin: 16mm; } }`;

  return { title: "Skills & Brag Sheet", html, css, printable: true };
}

// ---- Registry -------------------------------------------------------------

export const DOC_TYPES = [
  { id: "portfolio", name: "Portfolio Site", desc: "Responsive single-page site with projects & languages.", render: renderPortfolio },
  { id: "cv", name: "Technical CV", desc: "Print-ready one-page technical CV.", render: renderCV },
  { id: "cover", name: "Cover Letter", desc: "AI-drafted, editable cover letter.", render: renderCoverLetter },
  { id: "brag", name: "Skills / Brag Sheet", desc: "Quantified achievements & skill matrix.", render: renderBragSheet },
];
