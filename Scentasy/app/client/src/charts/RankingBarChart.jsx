import React from "react";
import { ACCENT, SEASON_COLORS, GRID, LABEL, INK } from "./palette.js";

// Horizontal bars: Fragella returns these already ordered best-to-worst with
// wordy labels ("night out", "professional"), which vertical bars can only fit
// by shrinking the text to the point of uselessness.
const W = 420;
const ROW_H = 34;
const BAR_H = 16;
const LABEL_W = 104;
const VALUE_W = 34;
const TOP_PAD = 6;

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

/**
 * `data` is [{ name, score }] ordered best first.
 * `colorBy="season"` gives each season its own colour; otherwise every bar
 * uses the accent, since occasions have no natural colour mapping.
 */
function RankingBarChart({ data, max = 3, colorBy }) {
  if (!data || !data.length) return null;

  const rows = data.filter((d) => d && d.name);
  if (!rows.length) return null;

  const height = TOP_PAD * 2 + rows.length * ROW_H;
  const trackX = LABEL_W;
  const trackW = W - LABEL_W - VALUE_W;

  const colorFor = (name) =>
    colorBy === "season"
      ? SEASON_COLORS[String(name).toLowerCase()] || ACCENT
      : ACCENT;

  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      className="ranking-chart"
      style={{ maxWidth: `${W}px` }}
      role="img"
      aria-label={rows
        .map((d) => `${capitalize(d.name)}: ${Number(d.score).toFixed(2)} out of ${max}`)
        .join(", ")}
    >
      {rows.map((d, i) => {
        const score = Number(d.score) || 0;
        const ratio = Math.max(0, Math.min(score / max, 1));
        const y = TOP_PAD + i * ROW_H;
        const barY = y + (ROW_H - BAR_H) / 2;
        const fill = colorFor(d.name);

        return (
          <g key={`${d.name}-${i}`}>
            <text
              x={LABEL_W - 12}
              y={barY + BAR_H / 2}
              textAnchor="end"
              dominantBaseline="middle"
              className="bar-label"
              fill={INK}
            >
              {capitalize(d.name)}
            </text>

            {/* empty track, so a low score still reads as "out of" something */}
            <rect
              x={trackX}
              y={barY}
              width={trackW}
              height={BAR_H}
              rx={BAR_H / 2}
              fill={GRID}
            />
            <rect
              x={trackX}
              y={barY}
              width={Math.max(BAR_H, trackW * ratio)}
              height={BAR_H}
              rx={BAR_H / 2}
              fill={fill}
            >
              <title>{`${capitalize(d.name)}: ${score.toFixed(2)} / ${max}`}</title>
            </rect>

            <text
              x={W - 4}
              y={barY + BAR_H / 2}
              textAnchor="end"
              dominantBaseline="middle"
              className="bar-value"
              fill={LABEL}
            >
              {score.toFixed(1)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default RankingBarChart;
