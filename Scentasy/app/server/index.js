const express = require("express");
const cors = require("cors");

const app = express();
const PORT = process.env.PORT || 8080;

const FRAGELLA_API_KEY = process.env.FRAGELLA_API_KEY;
const FRAGELLA_BASE_URL = "https://api.fragella.com/api/v1";

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.send("Hello from Scentasy server!");
});

// Search proxy. The browser calls this instead of Fragella directly so the
// API key stays on the server and never ships in the client bundle.
app.get("/api/fragrances", async (req, res) => {
  const search = (req.query.search || "").trim();

  if (!search) {
    return res.status(400).json({ message: "A search term is required." });
  }

  if (!FRAGELLA_API_KEY) {
    console.error("FRAGELLA_API_KEY is not set - copy .env.example to .env");
    return res
      .status(500)
      .json({ message: "Server is missing its Fragella API key." });
  }

  try {
    const response = await fetch(
      `${FRAGELLA_BASE_URL}/fragrances?search=${encodeURIComponent(search)}`,
      {
        headers: {
          "Content-Type": "application/json",
          "x-api-key": FRAGELLA_API_KEY,
        },
      },
    );

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        message: data.message || "Fragella rejected that request.",
      });
    }

    res.json(data);
  } catch (error) {
    console.error("Fragella request failed:", error);
    res.status(502).json({ message: "Could not reach the fragrance service." });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  if (!FRAGELLA_API_KEY) {
    console.warn("Warning: FRAGELLA_API_KEY is not set. Searches will fail.");
  }
});
