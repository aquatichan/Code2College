import React, { useState } from "react";
import { Container, InputGroup, FormControl, Button } from "react-bootstrap";
import SplashCursor from "./splash-cursor.jsx";
import TextPressure from "./text-pressure.jsx";
import RotatingText from "./rotating-text.jsx";
import FragranceCard from "./FragranceCard.jsx";
import "./index.css"; // global styles for Scentasy

function App() {
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const search = async () => {
    if (!searchInput.trim()) return;

    setIsLoading(true);

    try {
      // the server holds the Fragella key and forwards the request for us
      const response = await fetch(
        "/api/fragrances?search=" + encodeURIComponent(searchInput),
      );
      const data = await response.json();

      if (Array.isArray(data)) {
        setSearchResults(data);
        setErrorMessage(data.length ? "" : "No fragrances matched that search.");
      } else {
        setSearchResults([]);
        setErrorMessage(data?.message || "Unexpected response from server");
      }
    } catch (error) {
      console.error("Error searching fragrances:", error);
      setSearchResults([]);
      setErrorMessage("Could not reach the server. Is it running?");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* splash cursor effect over the entire viewport */}
      <SplashCursor className="splash-cursor-canvas" />

      <Container className="py-4">
        <div style={{ position: "relative", height: "300px" }}>
          <TextPressure
            text="Scentasy"
            flex
            alpha={false}
            stroke={false}
            width
            weight
            italic
            textColor="#000000"
            strokeColor="#000000"
            minFontSize={12}
          />
        </div>

        <div
          className="d-flex justify-content-center align-items-center"
          style={{ minHeight: "200px", flexWrap: "wrap", gap: "12px" }}
        >
          <span
            style={{
              fontSize: "2rem",
              fontWeight: "300",
              fontFamily: "system-ui, -apple-system, sans-serif",
              letterSpacing: "0em",
            }}
          >
            The
          </span>
          <div style={{ display: "inline-flex", alignItems: "center" }}>
            <RotatingText
              texts={[
                "ULTIMATE",
                "BEST",
                "MOST NICHE",
                "MOST EXCLUSIVE",
                "HIGHEST QUALITY",
                "MOST EXOTIC",
                "MOST UNIQUE",
                "MOST ICONIC",
                "LARGEST",
                "MOST USER-FRIENDLY",
                "MOST TRUSTED",
              ]}
              mainClassName="px-2 bg-primary text-white overflow-hidden py-2 rounded-lg"
              splitBy="words"
              staggerFrom="first"
              initial={{ y: "100%", opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: "-120%", opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              rotationInterval={2000}
              style={{
                fontSize: "2rem",
                fontWeight: "600",
                fontFamily: "system-ui, -apple-system, sans-serif",
              }}
            />
          </div>
          <span
            style={{
              fontSize: "2rem",
              fontWeight: "300",
              fontFamily: "system-ui, -apple-system, sans-serif",
              letterSpacing: "0em",
            }}
          >
            fragrance/perfume/cologne finder.
          </span>
        </div>

        <div className="mb-3">
          <InputGroup size="lg">
            <FormControl
              placeholder="Search for fragrances by name"
              value={searchInput}
              type="input"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  search();
                }
              }}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <Button variant="primary" onClick={search} disabled={isLoading}>
              {isLoading ? "Searching..." : "Search"}
            </Button>
          </InputGroup>
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="search-results-container">
            <h3 style={{ textAlign: "center", marginBottom: "30px" }}>
              Found {searchResults.length} fragrance
              {searchResults.length !== 1 ? "s" : ""}
            </h3>
            {searchResults.map((fragrance, index) => (
              <FragranceCard key={index} fragrance={fragrance} />
            ))}
          </div>
        )}

        {searchResults.length === 0 && !isLoading && !errorMessage && (
          <div className="search-empty-state">
            <p>Search for a fragrance to get started</p>
          </div>
        )}

        {errorMessage && !isLoading && (
          <div className="search-error">
            <p>{errorMessage}</p>
          </div>
        )}
      </Container>
    </>
  );
}

export default App;
