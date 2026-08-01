// Chart colours for the fragrance card.
//
// Colour encodes meaning here rather than decorating: note tiers follow the
// perfumery pyramid (bright citrus opening -> floral heart -> woody base) and
// seasons use their own seasonal colours, so the hue itself carries data.

export const ACCENT = "#0f7d8d";
export const INK = "#141b1d";
export const MUTED = "#6b7c82";
export const HAIRLINE = "#e6ebec";

// Note pyramid: top notes flash bright and fade, base notes are the deep dry-down.
export const NOTE_TIERS = [
  { key: "Top", label: "Top", color: "#e0a03c", weight: 3 },
  { key: "Middle", label: "Heart", color: "#c4657f", weight: 2.3 },
  { key: "Base", label: "Base", color: "#4f5f96", weight: 1.7 },
];

// Fragella grades accords on four discrete steps, so the radar uses a 0-4
// scale and its rings land exactly on the grades.
export const ACCORD_STRENGTHS = ["Subtle", "Moderate", "Prominent", "Dominant"];
export const ACCORD_MAX = 4;

export const ACCORD_VALUES = {
  Dominant: 4,
  Prominent: 3,
  Moderate: 2,
  Subtle: 1,
};

// Seasons carry their own colour; anything unrecognised falls back to accent.
export const SEASON_COLORS = {
  spring: "#6aa84f",
  summer: "#e0a03c",
  fall: "#c1622e",
  autumn: "#c1622e",
  winter: "#5580a8",
};

export const GRID = "#e6ebec";
export const GRID_STRONG = "#cfd8da";
export const LABEL = "#6b7c82";
