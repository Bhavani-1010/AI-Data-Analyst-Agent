"""
app.py
Day 3: Flask API that wraps agent.py so the React frontend can talk to it
over HTTP instead of the terminal.
Day 4: Made deployment-ready (dynamic port, configurable CORS origin).

Endpoints:
  POST /ask            -> {"question": "..."} => {"answer": "...", "chart_url": "..." or null}
  GET  /charts/<file>  -> serves a generated chart PNG
  GET  /reports/<file> -> serves a generated Excel report

Local run: python app.py
(Keep this running in one terminal, and `npm run dev` in the React folder
 running in a second terminal, at the same time.)
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import agent  # our existing agent.py - reused as-is, not rewritten

app = Flask(__name__)

# In local dev, allow any origin (simplest). In production, set the
# FRONTEND_URL environment variable to your real Vercel URL so only your
# frontend can call this API - not just anyone on the internet.
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    CORS(app, origins=[frontend_url])
else:
    CORS(app)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "No question provided."}), 400

    agent.reset_last_chart()   # clear any chart path left over from a previous request
    agent.reset_last_report()  # same for reports

    try:
        result = agent.agent_executor.invoke({"input": question})
        answer_text = result["output"]
    except Exception as e:
        return jsonify({"error": f"Agent error: {e}"}), 500

    chart_path = agent.get_last_chart_path()  # e.g. "charts/chart_abc123.png", or None
    chart_url = None
    if chart_path:
        filename = chart_path.split("/")[-1].split("\\")[-1]  # works on Windows and Mac/Linux
        chart_url = f"/charts/{filename}"

    report_path = agent.get_last_report_path()  # e.g. "reports/report_abc123.csv", or None
    report_url = None
    if report_path:
        filename = report_path.split("/")[-1].split("\\")[-1]
        report_url = f"/reports/{filename}"

    return jsonify({
        "answer": answer_text,
        "chart_url": chart_url,
        "report_url": report_url,
    })


@app.route("/charts/<path:filename>")
def serve_chart(filename):
    return send_from_directory(agent.CHARTS_DIR, filename)


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(agent.REPORTS_DIR, filename, as_attachment=True)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # Render assigns its own PORT at runtime
    app.run(host="0.0.0.0", debug=False, port=port)
