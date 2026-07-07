// Animated line-node background. Faint constellation of nodes connected by lines;
// nodes drift, connect when near, and lean toward the cursor on hover. Colors are
// read from CSS custom properties so it tracks the light/dark theme automatically.

export function startBackground(canvas) {
  const ctx = canvas.getContext("2d");
  let width = 0, height = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
  const mouse = { x: -9999, y: -9999, active: false };
  let nodes = [];

  function themeColors() {
    const s = getComputedStyle(document.documentElement);
    return {
      line: s.getPropertyValue("--node-line").trim() || "rgba(120,120,120,.15)",
      dot: s.getPropertyValue("--node-dot").trim() || "rgba(120,120,120,.5)",
    };
  }
  let colors = themeColors();

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Node count scales with viewport area, capped for perf.
    const count = Math.min(90, Math.floor((width * height) / 16000));
    nodes = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
    }));
  }

  const LINK_DIST = 130;
  const MOUSE_DIST = 200;

  function step() {
    ctx.clearRect(0, 0, width, height);

    for (const n of nodes) {
      n.x += n.vx; n.y += n.vy;
      // Wrap around edges.
      if (n.x < -20) n.x = width + 20; else if (n.x > width + 20) n.x = -20;
      if (n.y < -20) n.y = height + 20; else if (n.y > height + 20) n.y = -20;

      // Gentle pull toward the cursor when hovering.
      if (mouse.active) {
        const dx = mouse.x - n.x, dy = mouse.y - n.y;
        const d = Math.hypot(dx, dy);
        if (d < MOUSE_DIST && d > 1) {
          const pull = (1 - d / MOUSE_DIST) * 0.04;
          n.x += dx * pull * 0.05;
          n.y += dy * pull * 0.05;
        }
      }
    }

    // Links between nearby nodes.
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy);
        if (d < LINK_DIST) {
          const alpha = 1 - d / LINK_DIST;
          ctx.strokeStyle = withAlpha(colors.line, alpha);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    // Links from cursor to nearby nodes (the hover response).
    if (mouse.active) {
      for (const n of nodes) {
        const d = Math.hypot(mouse.x - n.x, mouse.y - n.y);
        if (d < MOUSE_DIST) {
          ctx.strokeStyle = withAlpha(colors.dot, (1 - d / MOUSE_DIST) * 0.6);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(mouse.x, mouse.y);
          ctx.lineTo(n.x, n.y);
          ctx.stroke();
        }
      }
    }

    // Nodes.
    for (const n of nodes) {
      ctx.fillStyle = colors.dot;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 1.6, 0, Math.PI * 2);
      ctx.fill();
    }

    requestAnimationFrame(step);
  }

  // Multiply the alpha of an existing rgba()/hex color by a factor.
  function withAlpha(color, factor) {
    const m = color.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const parts = m[1].split(",").map((s) => s.trim());
      const base = parts.length === 4 ? parseFloat(parts[3]) : 1;
      return `rgba(${parts[0]},${parts[1]},${parts[2]},${(base * factor).toFixed(3)})`;
    }
    return color;
  }

  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", (e) => {
    mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true;
  });
  window.addEventListener("pointerleave", () => { mouse.active = false; });
  // Re-read colors when the theme flips.
  const obs = new MutationObserver(() => { colors = themeColors(); });
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    colors = themeColors();
  });

  resize();
  step();
}
