I am a core staff member of the student-run MathEXplained Magazine (https://mathexplained.github.io/) organization, where we author math spreads (compiled into monthly magazine releases) and math crossword puzzles to help make mathematics more accessible to general audiences. Our mission is to make math engaging and approachable by covering contemporary mathematical topics, exploring interesting ideas, and demonstrating that mathematics is not just for specialists, but something anyone can enjoy and learn from.

This Discord bot was primarily my idea and implementation. I wanted to create a centralized platform that would both automate server moderation—such as spam detection and handling—and foster engagement among the organization's ~140 Discord members through interactive mathematical activities.

While the current production bot resides in a private repository and has continued to evolve, this repository contains the first iteration of the project. It implements 20 Discord slash commands—spanning a moderated crowdsourced problem database, live multiplayer math duels, LaTeX rendering, persistent leaderboards, contributor workflows, moderation utilities, and community feedback tools—which are all visible in the sectioned tables below. Several additional features are included as scaffolds for future development, including Asymptote rendering, crossword integration, and Problem of the Week support.

## 📚 Problems

| Command | Description |
|----------|-------------|
| `/randproblem` | View a random approved problem from a selected category |
| `/problem` | View a specific problem by ID |
| `/submitproblem` | Submit a new problem for moderator review |
| `/reportproblem` | Report an incorrect or broken problem |
| `/stats` | View statistics about the problem database |

---

## ⚔️ Duels

| Command | Description |
|----------|-------------|
| `/duelgame` | Challenge another user or the bot to a live math duel |
| `/leaderboard` | View the top duel players |
| `/duelstats` | View your personal duel record |

---

## ✏️ Rendering

| Command | Description |
|----------|-------------|
| `/renderlatex` | Render LaTeX expressions into high-resolution images |
| `/renderasy` | Render Asymptote diagrams *(scaffold)* |

---

## 🌐 General

| Command | Description |
|----------|-------------|
| `/help` | Display all available commands |
| `/ping` | Check bot latency |
| `/feedback` | Send feedback to the development team |
| `/website` | Visit the MathEXplained website (https://mathexplained.github.io/)|
| `/apply` | Apply to become a MathEXplained staff member |

---

## 🛠 Moderator Commands

| Command | Description |
|----------|-------------|
| `/reviewproblem` | Review pending submissions |
| `/editproblem` | Browse and edit the problem database |
| `/deleteproblem` | Permanently delete a problem |
| `/offenses` | View a member's moderation history |
