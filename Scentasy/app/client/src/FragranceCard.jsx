import React, { useState } from "react";
import RadarChart from "./charts/RadarChart.jsx";
import NotesPackChart from "./charts/NotesPackChart.jsx";
import RankingBarChart from "./charts/RankingBarChart.jsx";
import PeopleRating from "./charts/PeopleRating.jsx";
import { ACCORD_VALUES } from "./charts/palette.js";
import "./charts/charts.css";
import "./FragranceCard.css";

// Fragella's ranking scores are unbounded in the docs but observed well under
// 3 (the published examples top out at 2.98), so both charts share that scale
// and stay comparable between fragrances.
const RANKING_MAX = 3;

// A radar stops being readable past about eight axes.
const MAX_ACCORD_AXES = 8;

const longevityDescriptions = {
  "Very Long Lasting": "Over 12 hours",
  "Long Lasting": "8 to 12 hours",
  Moderate: "4 to 7 hours",
  Weak: "2 to 3 hours",
  Poor: "Under 2 hours",
};

const sillageDescriptions = {
  Enormous: "Fills a room",
  Strong: "Projects beyond arm's length",
  Moderate: "About arm's length",
  Soft: "Close to the skin, still noticed",
  Intimate: "Only on close contact",
};

const priceValueLabels = {
  good_value: "Good value",
  okay: "Fairly priced",
  overpriced: "Overpriced",
};

const capitalize = (s) =>
  typeof s === "string" && s ? s.charAt(0).toUpperCase() + s.slice(1) : "";

function NewTabIcon() {
  return (
    <svg
      width="1em"
      height="1em"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

/**
 * Fragella keeps accord strengths in a separate "Main Accords Percentage"
 * object keyed by accord name - the "Main Accords" array is just strings.
 * Strongest accords first, capped so the radar stays legible.
 */
function buildAccordAxes(fragrance) {
  const strengths = fragrance["Main Accords Percentage"];
  const names = fragrance["Main Accords"];

  if (strengths && typeof strengths === "object" && !Array.isArray(strengths)) {
    return Object.entries(strengths)
      .map(([label, grade]) => ({ label, value: ACCORD_VALUES[grade] || 0 }))
      .filter((a) => a.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, MAX_ACCORD_AXES);
  }

  // Older/partial payloads only carry the name list, with no strengths at all.
  if (Array.isArray(names)) {
    return names
      .filter((n) => typeof n === "string" && n)
      .slice(0, MAX_ACCORD_AXES)
      .map((label) => ({ label, value: 0 }));
  }

  return [];
}

function BottleImage({ fragrance }) {
  // The transparent .webp composites onto the card; the plain .jpg has a
  // baked-in solid background that reads as a box inside a box.
  const sources = [
    fragrance["Image URL Transparent"],
    fragrance["Image URL"],
    ...(Array.isArray(fragrance["Image Fallbacks"])
      ? fragrance["Image Fallbacks"]
      : []),
  ].filter(Boolean);

  const [index, setIndex] = useState(0);

  if (!sources.length || index >= sources.length) {
    return <div className="fc-bottle fc-bottle-missing">No image</div>;
  }

  return (
    <img
      src={sources[index]}
      alt={fragrance.Name || "Fragrance bottle"}
      className="fc-bottle"
      loading="lazy"
      onError={() => setIndex((i) => i + 1)}
    />
  );
}

function WearStat({ label, value, descriptions }) {
  if (!value) return null;
  return (
    <div className="fc-wear-stat">
      <p className="fc-label">{label}</p>
      <p className="fc-wear-value">{value}</p>
      {descriptions[value] && (
        <p className="fc-wear-detail">{descriptions[value]}</p>
      )}
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="fc-section">
      <h3 className="fc-section-title">{title}</h3>
      {children}
    </section>
  );
}

function FragranceCard({ fragrance }) {
  if (!fragrance) return null;

  const accords = buildAccordAxes(fragrance);
  const gradedAccords = accords.filter((a) => a.value > 0);
  const seasons = fragrance["Season Ranking"];
  const occasions = fragrance["Occasion Ranking"];
  const purchaseUrl = fragrance["Purchase URL"];
  const rating = parseFloat(fragrance.rating);
  const priceValue = priceValueLabels[fragrance["Price Value"]];
  const generalNotes = fragrance["General Notes"];

  const hasPyramid =
    fragrance.Notes &&
    ["Top", "Middle", "Base"].some(
      (tier) => Array.isArray(fragrance.Notes[tier]) && fragrance.Notes[tier].length,
    );

  // "Eau de Parfum · 2014 · Men"
  const subtitle = [
    fragrance.OilType,
    fragrance.Year,
    capitalize(fragrance.Gender),
  ].filter(Boolean);

  const hasWearRow =
    fragrance.Longevity || fragrance.Sillage || Number.isFinite(rating);

  return (
    <article className="fragrance-card">
      <header className="fc-header">
        <div className="fc-bottle-frame">
          <BottleImage fragrance={fragrance} />
        </div>

        <div className="fc-identity">
          {fragrance.Brand && <p className="fc-brand">{fragrance.Brand}</p>}
          <h2 className="fc-name">{fragrance.Name}</h2>

          {subtitle.length > 0 && (
            <p className="fc-subtitle">{subtitle.join(" · ")}</p>
          )}

          {(Number.isFinite(rating) || fragrance.Price) && (
            <div className="fc-facts">
              {Number.isFinite(rating) && (
                <div className="fc-fact">
                  <span className="fc-fact-value">{rating.toFixed(2)}</span>
                  <span className="fc-fact-label">out of 5</span>
                </div>
              )}
              {fragrance.Price && (
                <div className="fc-fact">
                  <span className="fc-fact-value">${fragrance.Price}</span>
                  <span className="fc-fact-label">
                    {priceValue || "average retail"}
                  </span>
                </div>
              )}
            </div>
          )}

          {purchaseUrl && (
            <a
              href={purchaseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="fc-buy"
            >
              View purchase options <NewTabIcon />
            </a>
          )}

          {(fragrance.Popularity || fragrance.Confidence) && (
            <p className="fc-provenance">
              {fragrance.Popularity && <>{fragrance.Popularity} popularity</>}
              {fragrance.Popularity && fragrance.Confidence && " · "}
              {fragrance.Confidence && <>{fragrance.Confidence} data confidence</>}
            </p>
          )}
        </div>
      </header>

      {(gradedAccords.length >= 3 || hasPyramid || accords.length > 0) && (
        <Section title="Scent profile">
          <div className="fc-duo">
            <div className="fc-panel">
              <h4 className="fc-label">Main accords</h4>
              {gradedAccords.length >= 3 ? (
                <RadarChart data={gradedAccords} />
              ) : (
                <ul className="fc-chip-list">
                  {accords.map((a) => (
                    <li key={a.label} className="fc-chip">
                      {capitalize(a.label)}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="fc-panel">
              <h4 className="fc-label">Note pyramid</h4>
              {hasPyramid ? (
                <NotesPackChart notes={fragrance.Notes} />
              ) : Array.isArray(generalNotes) && generalNotes.length ? (
                <ul className="fc-chip-list">
                  {generalNotes.map((note) => (
                    <li key={note} className="fc-chip">
                      {capitalize(note)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fc-empty">No note breakdown available.</p>
              )}
            </div>
          </div>
        </Section>
      )}

      {hasWearRow && (
        <Section title="How it wears">
          <div className="fc-trio">
            <WearStat
              label="Longevity"
              value={fragrance.Longevity}
              descriptions={longevityDescriptions}
            />
            <WearStat
              label="Sillage"
              value={fragrance.Sillage}
              descriptions={sillageDescriptions}
            />
            {Number.isFinite(rating) && (
              <div className="fc-wear-stat">
                <p className="fc-label">Reception</p>
                <PeopleRating rating={rating} />
              </div>
            )}
          </div>
        </Section>
      )}

      {(seasons?.length > 0 || occasions?.length > 0) && (
        <Section title="When to wear it">
          <div className="fc-duo">
            {seasons?.length > 0 && (
              <div className="fc-panel">
                <h4 className="fc-label">By season</h4>
                <RankingBarChart
                  data={seasons}
                  max={RANKING_MAX}
                  colorBy="season"
                />
              </div>
            )}
            {occasions?.length > 0 && (
              <div className="fc-panel">
                <h4 className="fc-label">By occasion</h4>
                <RankingBarChart data={occasions} max={RANKING_MAX} />
              </div>
            )}
          </div>
        </Section>
      )}
    </article>
  );
}

export default FragranceCard;
