# AI Data Analyst Agent

An AI-powered data analyst that answers natural-language questions over sales and tabular datasets using automated SQL queries, statistical calculations, visual charts, and formatted Excel reports.

## ⚡ Use as an AI Agent Skill (Claude Code, Cursor, Codex CLI)

Want to use this directly inside your AI coding agent with **zero setup, no Flask server, and no external API keys**? Grab the plug-and-play `SKILL.md` package on **Agensi.io**:

👉 **[Get the AI Data Analyst Agent Skill on Agensi.io](YOUR_AGENSI_LINK)**

### Skill Capabilities
* **Automated Schema & Data Cleaning:** Inspects CSV and SQLite files, cleans formatted numbers, and normalizes dates automatically.
* **Natural-Language SQL & Pandas:** Runs aggregations, rankings, correlations, and growth metrics locally on your data.
* **Charts & Excel Deliverables:** Generates high-resolution `matplotlib` PNG charts and formatted `.xlsx` spreadsheets with native embedded bar charts.

---

## 🛠️ Full-Stack Web App (Local Setup)

This repository also contains the full-stack web version built with **LangChain, Groq, Flask, SQLite, and React**:

1. **Build the SQLite database:**
   ```bash
   python build_db.py
   ```
2. **Start the Flask backend:**
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
3. **Run the React frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
