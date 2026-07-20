# 2026-2027 Code2College Project Portfolio

## 📋 Index

This portfolio is arranged by date of project creation.

| Code | Project | Type | Last Updated |
|------|---------|------|--------------|
| **HS** | Hirewheel Scraper | Student Opportunity Scraper | 7/20/26 |
| **DD** | DirDelta | Directory Comparison CLI | 7/7/26 |
| **PF** | Portfolix Studio | GitHub Portfolio Generator | 7/7/26 |
| **SC** | Sunset Cafe Website | Responsive Business Website | 6/19/26 |
| **RE** | Runtime Escape | Educational Dungeon Crawler | 6/13/26 |
| **M3** | MP3'd | 3D Synthwave Rhythm Game | 6/11/26 |

> Use **Ctrl+F** (Windows/Linux) or **⌘+F** (Mac) to search a project's two-letter code (as in the table above) for quick navigation.

---
---
---

## 6. 🧑‍💻 Hirewheel Scraper [HS]
> **Last Updated:** 7/20/26

| Category | Information |
|-----------|-------------|
| **Project** | Hirewheel Scraper |
| **Type** | Student Opportunity Scraper |
| **Platform** | Python Desktop Application |
| **Built With** | Python, Playwright, Tkinter |

---

**Hirewheel Scraper** is a desktop monitoring tool built for **Code2College students** that continuously watches important Hirewheel pages and alerts users whenever new opportunities appear. Instead of repeatedly checking the portal manually, it performs periodic scans, compares each page against previous snapshots, and displays only newly added, changed, or removed content.

Using a persistent Playwright browser session, the scraper securely reuses the user's own authenticated login (including MFA) without storing credentials. A built-in Tkinter dashboard groups detected changes by page and displays screenshots of each modified page, making it easy to review internship opportunities, marketplace projects, surveys, notifications, events, and news at a glance.

Read the full README.md for local setup/usage: **[Click me!](hirewheel_scraper/README.md)**

### ✨ Features

| | |
|---|---|
| 👀 | Automatically monitors **11 Hirewheel pages** including Notifications, Marketplace, Newsfeed, Surveys, Events, Learning Modules, etc. |
| 🔐 | Uses a real **Playwright browser session** so credentials and MFA remain handled by Hirewheel |
| 🔄 | Performs background scans every **3 hours**, automatically comparing each page against previous snapshots |
| 📌 | Detects **added, changed, and removed** content using stable HTML identifiers for highly accurate diffs |
| 🖼️ | Displays an interactive **Tkinter desktop dashboard** with inline screenshots for every changed page |
| 💾 | Stores per-page JSON snapshots locally to efficiently track historical changes |
| 🚀 | Runs headlessly after the initial login with virtually no user interaction required |
| 🧪 | Includes extractor and pipeline tests covering **all 11 page extractors** for reliable monitoring |

---
---
---

## 5. 📈📉 DirDelta [DD]
> **Last Updated:** 7/7/26

| Category | Information |
|-----------|-------------|
| **Project** | DirDelta |
| **Type** | Directory Comparison CLI |
| **Platform** | Python CLI |
| **Built With** | Python Standard Library |

---

**DirDelta** is a command-line directory comparison tool that recursively analyzes two directory trees and generates a clean, structured change report. It classifies files as **Added**, **Removed**, **Modified**, or **Unchanged** using SHA-256 content verification, while supporting unified diffs, ignore patterns, and JSON exports for automation workflows.

Designed for engineering workflows like backup verification, deployment auditing, and release comparisons, DirDelta prioritizes accurate file analysis, low-noise reporting, and easy integration into scripts or CI pipelines.

Read the full README.md for local setup/usage: [Click me!](dirdelta/README.md)

### ✨ Features

| | |
|---|---|
| 🔍 | Recursively compares **entire directory trees** and matches files by relative path |
| 🔐 | Uses **SHA-256 hashing** for content-accurate modification detection |
| 📂 | Classifies files into **Added, Removed, Modified, and Unchanged** categories |
| 📝 | Generates optional **unified text diffs** while automatically detecting binary files |
| 🚫 | Supports built-in and custom **ignore patterns** for filtering unnecessary files |
| 📊 | Provides detailed **summary statistics** including extension breakdowns |
| 📄 | Exports complete comparison reports as **machine-readable JSON** |
| 🐍 | Zero dependencies — built entirely with the **Python standard library** |

---
---
---

## 4. 💼 Portfolix [PF]
> **Last Updated:** 7/7/26

| Category | Information |
|-----------|-------------|
| **Project** | Portfolix |
| **Type** | GitHub Portfolio Generator |
| **Platform** | Web + Python CLI |
| **Built With** | Python, HTML, CSS, JavaScript |

---

**Portfolix** automatically transforms a developer's public GitHub profile into professional portfolio materials using the GitHub API. A Python CLI collects repository statistics, featured projects, and language data, then generates a single JSON file powering an interactive web studio where users can create and customize portfolio websites, technical CVs, cover letters, and skills summaries.

The project combines automated GitHub data collection with optional AI-enhanced writing and an in-browser editor, allowing developers to generate polished application materials without manually rebuilding them whenever their projects change.

Read the full README.md for local setup/usage: [Click me!](Portfolix/README.md)

### ✨ Features

| | |
|---|---|
| 📊 | Automatically imports **GitHub repositories, languages, and project statistics** |
| 🌐 | Generates **portfolio websites, technical CVs, cover letters, and skills sheets** from a single data source |
| 🤖 | Optional **AI-enhanced writing** for bios, project descriptions, and application materials |
| ✏️ | Built-in **live HTML & CSS editor** with instant preview and customization |
| 🎨 | AI-powered **Beautify** mode for automatic themes, typography, and styling |
| 📱 | Responsive interface with animated backgrounds and light/dark theme support |
| 💡 | Fully static front-end powered by a generated **JSON** file with no backend required |
| 🔄 | Easily regenerate documents anytime by rerunning the Python CLI |


---
---
---

## 3. ☀️ Sunset Cafe Website [SC]
> **Last Updated:** 6/19/26

| Category | Information |
|-----------|-------------|
| **Project** | Sunset Cafe Website |
| **Type** | Responsive Business Website |
| **Platform** | Web |
| **Built With** | HTML, CSS, JavaScript |

---

**Sunset Cafe Website** is a fully responsive promotional website built for a fictional neighborhood café and bakery, designed to showcase its menu, atmosphere, and local identity through a modern, warm, and inviting interface. The site combines elegant typography, high-quality photography, and subtle animations to create the feeling of visiting a cozy brunch destination.

Visitors can explore the restaurant's featured brunch dishes, bakery items, and specialty drinks through an organized menu layout, browse a gallery of food and interior photography, read customer testimonials, and quickly access business hours, location information, and online ordering. The landing page features smooth scrolling navigation to provide a polished user experience across desktop and mobile devices.

The project emphasizes responsive web design, accessibility, performance optimization, and modern front-end development practices while demonstrating how a small business can establish a professional online presence using only HTML, CSS, and JavaScript.

### ✨ Features
| | |
|---|---|
| 📲 | **Responsive café website** optimized for desktop, tablet, and mobile devices |
| 🥞 | Beautifully organized **menu sections** featuring brunch, bakery, and drink offerings |
| 🖼️ | Interactive **photo gallery** showcasing food and café atmosphere |
| ✨ | Animated hero section with **parallax scrolling effects** and smooth page transitions |
| 📍 | Business hours, contact information, and embedded location section for easy customer access |
| ⭐ | Customer testimonial section highlighting the café experience |
| 🛒 | Integrated **online ordering button** for future e-commerce compatibility |
| 🌐 | Built entirely with **HTML, CSS, and JavaScript** with no frameworks or build process required |

---
---
---

## 2. 👹 Runtime Escape [RE]
> **Last Updated:** 6/13/26

| Category | Information |
|-----------|-------------|
| **Project** | Runtime Escape |
| **Type** | Educational Dungeon Crawler |
| **Platform** | Browser |
| **Built With** | HTML, CSS, JavaScript |

---

**Runtime Escape** is a browser-based dungeon crawler that transforms programming concepts into fast-paced action puzzles. Players descend through six procedurally generated worlds, each themed around a fundamental computer science topic, collecting scattered code fragments while avoiding bugs, hazards, and corrupted entities lurking throughout the system.

Every world introduces a unique mechanic inspired by programming itself—from branching conditionals and looping enemies to maze-like list structures, sweeping laser grids, and an epic final battle against the Stack Overflow. Completing each stage requires mastering its gimmick while assembling enough code fragments to repair the program and escape before the runtime collapses.

The game blends arcade gameplay with educational themes, presenting coding ideas through interactive mechanics rather than traditional tutorials. As players progress deeper into the corrupted runtime, each level becomes more challenging, culminating in a final boss fight where combat and programming collide.

### ✨ Features
| | |
|---|---|
| 🏰 | **Six unique worlds**, each centered around a different computer science concept |
| 💾 | **Collect hidden code fragments** to repair the program and unlock the next stage |
| 🎲 | **Procedurally generated levels** for fresh layouts every playthrough |
| 👾 | Multiple enemy types, environmental hazards, and world-specific gimmicks |
| 🌀 | Programming-inspired mechanics including conditionals, loops, lists, laser grids, and boss combat |
| ⚔️ | Real-time movement and melee combat with keyboard or on-screen controls |
| 🧩 | Educational themes presented through gameplay rather than direct instruction |
| 🌐 | Runs entirely in the browser with **no installation or build process required** |

---
---
---

## 1. 🎵 MP3'd [M3]
> **Last Updated:** 6/11/26

| Category | Information |
|-----------|-------------|
| **Project** | MP3'd |
| **Type** | 3D Synthwave Rhythm Game |
| **Platform** | Browser |
| **Built With** | HTML, CSS, JavaScript |

---

**MP3'd** is a 3D synthwave rhythm game that turns any MP3 into a playable music experience. Players drive a neon sports car through a retro-futuristic sunset while steering between lanes and hitting rhythm markers synchronized to the music.

The game supports both **AI-powered beat mapping** (using Gemini) and a fully offline spectral-flux beat detector, allowing custom songs to be converted into playable charts in seconds. Every track becomes a unique driving challenge where positioning and timing matter equally.

As you land perfect hits, your car gradually comes alive—cycling through vibrant colors and glowing brighter with increasing alpha. Miss notes or collide with obstacles, and your car fades toward darkness until it ultimately shatters if its energy reaches zero. Survive until the final note to blaze into the horizon as a rainbow streak.

### ✨ Features
| | |
|---|---|
| 🚗 | **3D synthwave driving gameplay** with lane steering and rhythm mechanics |
| 🎵 | **Play your own MP3 files** by uploading custom songs |
| 🤖 | **AI-generated beat maps** with offline fallback detection |
| 🌈 | Dynamic color and alpha system that visually reflects performance |
| 🛣️ | Endless neon highway with obstacles and particle effects |
| 🎮 | Multiple car models, difficulty settings, and customizable controls |
| 🏆 | Local leaderboard support and persistent settings |
| 📄 | Entire game contained in a **single HTML file** with no build process required |

---
---
---