import React from "react";
import {
  ACCENT,
  GRID,
  GRID_STRONG,
  LABEL,
  ACCORD_MAX,
  ACCORD_STRENGTHS,
} from "./palette.js";

// The viewBox carries its own margin so long axis labels ("white floral")
// stay inside the box. Relying on overflow:visible clips inside a flex column.
const W = 440;
const H = 340;
const CX = W / 2;
const CY = 152;
const R = 96;

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

/**
 * Radar chart of a fragrance's accords.
 * `data` is [{ label, value }] where value is 1-4, matching Fragella's four
 * strength grades (Subtle, Moderate, Prominent, Dominant).
 */
function RadarChart({ data }) {
  if (!data || data.length < 3) return null;

  const angleAt = (i) => (Math.PI * 2 * i) / data.length - Math.PI / 2;

  const pointAt = (i, value) => {
    const r = (Math.max(0, Math.min(value, ACCORD_MAX)) / ACCORD_MAX) * R;
    const a = angleAt(i);
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
  };

  const ringPoints = (step) =>
    data
      .map((_, i) => {
        const a = angleAt(i);
        const r = (step / ACCORD_MAX) * R;
        return `${CX + r * Math.cos(a)},${CY + r * Math.sin(a)}`;
      })
      .join(" ");

  const shape = data.map((d, i) => pointAt(i, d.value).join(",")).join(" ");

  return (
    <figure className="chart-figure">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="radar-chart"
        role="img"
        aria-label={`Accord strengths: ${data
          .map((d) => `${d.label} ${ACCORD_STRENGTHS[d.value - 1] || d.value}`)
          .join(", ")}`}
      >
        {[1, 2, 3, 4].map((step) => (
          <polygon
            key={step}
            points={ringPoints(step)}
            fill="none"
            stroke={step === ACCORD_MAX ? GRID_STRONG : GRID}
            strokeWidth="1"
            strokeDasharray={step === ACCORD_MAX ? "none" : "2 4"}
          />
        ))}

        {data.map((d, i) => {
          const [x, y] = pointAt(i, ACCORD_MAX);
          return (
            <line
              key={d.label}
              x1={CX}
              y1={CY}
              x2={x}
              y2={y}
              stroke={GRID}
              strokeWidth="1"
            />
          );
        })}

        <polygon
          points={shape}
          fill={ACCENT}
          fillOpacity="0.22"
          stroke={ACCENT}
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {data.map((d, i) => {
          const [x, y] = pointAt(i, d.value);
          return (
            <circle key={d.label} cx={x} cy={y} r="3.5" fill={ACCENT}>
              <title>{`${capitalize(d.label)}: ${ACCORD_STRENGTHS[d.value - 1] || d.value}`}</title>
            </circle>
          );
        })}

        {/* Axis labels. Two-word accords wrap so they don't run into a neighbour. */}
        {data.map((d, i) => {
          const a = angleAt(i);
          const cos = Math.cos(a);
          const sin = Math.sin(a);
          const lx = CX + (R + 20) * cos;
          const ly = CY + (R + 20) * sin;
          const anchor = cos > 0.25 ? "start" : cos < -0.25 ? "end" : "middle";
          const words = capitalize(d.label).split(" ");
          const twoLine = words.length > 1;
          // nudge vertically so a wrapped label stays centred on its spoke
          const baseDy = twoLine ? -4 : 0;

          return (
            <text
              key={d.label}
              x={lx}
              y={ly + baseDy + (sin > 0.7 ? 5 : sin < -0.7 ? -5 : 0)}
              textAnchor={anchor}
              dominantBaseline="middle"
              className="radar-label"
              fill={LABEL}
            >
              {twoLine ? (
                <>
                  <tspan x={lx} dy="0">
                    {words[0]}
                  </tspan>
                  <tspan x={lx} dy="1.15em">
                    {words.slice(1).join(" ")}
                  </tspan>
                </>
              ) : (
                words[0]
              )}
            </text>
          );
        })}
      </svg>

      <figcaption className="chart-scale">
        {ACCORD_STRENGTHS.map((name, i) => (
          <span key={name} className="chart-scale-step">
            <span
              className="chart-scale-dot"
              style={{ opacity: 0.25 + i * 0.25 }}
            />
            {name}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

export default RadarChart;
