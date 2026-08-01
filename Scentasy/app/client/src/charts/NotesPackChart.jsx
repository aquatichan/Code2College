import React, { useMemo } from "react";
import { hierarchy, pack } from "d3-hierarchy";
import { NOTE_TIERS } from "./palette.js";

const W = 440;
const H = 300;

// Approximate width of one character relative to font size, for fitting
// labels inside their circle rather than letting them spill out.
const CHAR_RATIO = 0.54;

/**
 * Work out how a note's name should sit inside its circle: one line, wrapped
 * onto two, or omitted entirely when the circle is simply too small.
 */
function fitLabel(name, radius) {
  const fontSize = Math.max(9, Math.min(13, radius / 2.4));
  const chordAt = (offset) => 2 * Math.sqrt(Math.max(0, radius * radius - offset * offset));

  const fitsIn = (text, width) => text.length * fontSize * CHAR_RATIO <= width * 0.92;

  if (fitsIn(name, chordAt(0))) return { fontSize, lines: [name] };

  const words = name.split(" ");
  if (words.length > 1) {
    // two lines sit above and below centre, so each gets a shorter chord
    const chord = chordAt(fontSize * 0.62);
    const first = words[0];
    const rest = words.slice(1).join(" ");
    if (fitsIn(first, chord) && fitsIn(rest, chord)) {
      return { fontSize, lines: [first, rest] };
    }
  }

  return { fontSize, lines: null };
}

/**
 * Packed circle chart of the note pyramid. Circles are sized and coloured by
 * tier - bright top notes largest, deep base notes darkest.
 */
function NotesPackChart({ notes }) {
  const leaves = useMemo(() => {
    if (!notes) return [];

    const children = [];
    NOTE_TIERS.forEach((tier) => {
      const tierNotes = notes[tier.key];
      if (!Array.isArray(tierNotes)) return;
      tierNotes.forEach((note) => {
        const name = typeof note === "string" ? note : note?.name;
        if (!name) return;
        children.push({
          name,
          tier: tier.label,
          color: tier.color,
          value: tier.weight,
        });
      });
    });

    if (!children.length) return [];

    const root = hierarchy({ children }).sum((d) => d.value || 1);
    pack().size([W, H]).padding(6)(root);
    return root.leaves();
  }, [notes]);

  if (!leaves.length) return null;

  return (
    <figure className="chart-figure">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="notes-pack-svg"
        role="img"
        aria-label={`Note pyramid: ${leaves
          .map((leaf) => `${leaf.data.name} (${leaf.data.tier})`)
          .join(", ")}`}
      >
        {leaves.map((leaf, i) => {
          const { fontSize, lines } = fitLabel(leaf.data.name, leaf.r);
          return (
            <g
              key={`${leaf.data.name}-${i}`}
              transform={`translate(${leaf.x},${leaf.y})`}
            >
              <circle r={leaf.r} fill={leaf.data.color} fillOpacity="0.9">
                <title>{`${leaf.data.name} - ${leaf.data.tier} note`}</title>
              </circle>
              {lines && (
                <text
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={fontSize}
                  className="notes-pack-label"
                  y={lines.length > 1 ? -fontSize * 0.55 : 0}
                >
                  {lines.map((line, li) => (
                    <tspan key={li} x="0" dy={li === 0 ? 0 : "1.1em"}>
                      {line}
                    </tspan>
                  ))}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <figcaption className="chart-scale">
        {NOTE_TIERS.map((tier) => (
          <span key={tier.key} className="chart-scale-step">
            <span
              className="chart-scale-dot"
              style={{ backgroundColor: tier.color, opacity: 1 }}
            />
            {tier.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

export default NotesPackChart;
