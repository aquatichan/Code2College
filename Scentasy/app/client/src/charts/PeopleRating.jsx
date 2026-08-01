import React from "react";

const TOTAL_PEOPLE = 10;

function PersonIcon({ filled }) {
  return (
    <svg
      viewBox="0 0 24 26"
      className={`person-glyph ${filled ? "is-filled" : "is-empty"}`}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="5.5" r="3.6" />
      <path d="M12 10.4c-3.1 0-5.6 1.5-5.6 3.4v3.9h2l.6 5.3h2.2l.3-3.9h1l.3 3.9h2.2l.6-5.3h2v-3.9c0-1.9-2.5-3.4-5.6-3.4z" />
    </svg>
  );
}

/**
 * Fragella's rating is Bayesian out of 5.00, so doubling it reads naturally as
 * a count of people out of ten.
 */
function PeopleRating({ rating }) {
  const parsed = parseFloat(rating);
  if (!Number.isFinite(parsed)) return null;

  const outOfTen = Math.max(0, Math.min(10, Math.round(parsed * 2)));

  return (
    <div className="people-rating">
      <div
        className="people-rating-row"
        role="img"
        aria-label={`${outOfTen} out of ${TOTAL_PEOPLE} people would enjoy this scent`}
      >
        {Array.from({ length: TOTAL_PEOPLE }).map((_, i) => (
          <PersonIcon key={i} filled={i < outOfTen} />
        ))}
      </div>
      <p className="people-rating-text">
        <strong>{outOfTen} in {TOTAL_PEOPLE}</strong> would enjoy this on someone
      </p>
    </div>
  );
}

export default PeopleRating;
