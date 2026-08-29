"""
agent.py
Day 1: A LangChain SQL agent, powered by Groq's LLaMA model, that answers
plain-English questions against sales.db by writing and running its own SQL.
Day 2: Added a pandas calculation tool for stats SQL can't easily do
(correlation, percentage change, multi-step calculations, etc.), plus a
chart-generation tool that saves matplotlib charts as PNG files.

Run: python agent.py
"""

import os
import sqlite3
import uuid
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.tools import tool
# NOTE: pandas, matplotlib, and openpyxl are intentionally NOT imported here
# at the top of the file - they're only imported inside the functions that
# actually need them. This matters on memory-constrained hosting (e.g.
# Render's free 512MB tier): loading these libraries at startup for EVERY
# request - even a plain SQL lookup that never touches a DataFrame, chart,
# or report - was pushing the process over its memory limit and getting
# SIGKILLed by the OS. Lazy-loading them only when actually used keeps the
# baseline memory footprint much smaller, since most simple questions only
# ever need the lightweight SQL tool.
pd = None  # populated by _ensure_pandas() the first time any tool needs it

DB_PATH = "sales.db"
CHARTS_DIR = "charts"
REPORTS_DIR = "reports"
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ---- 1. Load the Groq API key from .env ----
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError(
        "GROQ_API_KEY not found. Make sure you have a .env file in this folder "
        "with a line like: GROQ_API_KEY=gsk_your_key_here"
    )

# ---- 2. Set up the LLM ----
llm = ChatGroq(
    groq_api_key=groq_api_key,
    model="qwen/qwen3.6-27b",  # gpt-oss-120b has a known bug where it tries to
    # call a built-in "python" tool Groq doesn't have enabled, breaking custom
    # tool calls. Kimi K2 (both versions) is fully deprecated on Groq as of 2026.
    # Qwen 3.6 27B is current, well-supported, and doesn't have this bias.
    temperature=0,  # deterministic output matters for SQL generation
)

# ---- 3. Connect to the SQLite database ----
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

# ---- 3b. Pandas calculation tool ----
# The full sales table, loaded once and cached, so the pandas tool doesn't
# re-read the whole database on every call.
_df_cache = None

def _ensure_pandas():
    """Imports pandas into the module-level `pd` name the first time it's
    needed, and does nothing on subsequent calls. Keeps pandas out of memory
    entirely for requests that only use the plain SQL tool."""
    global pd
    if pd is None:
        import pandas as pd_module
        pd = pd_module


def _get_dataframe():
    global _df_cache
    _ensure_pandas()
    if _df_cache is None:
        conn = sqlite3.connect(DB_PATH)
        _df_cache = pd.read_sql("SELECT * FROM sales", conn)
        conn.close()
    return _df_cache


@tool
def pandas_calculation_tool(code: str) -> str:
    """
    Use this tool ONLY for calculations that are hard or impossible to express
    in plain SQL - for example: correlation between two columns, percentage
    change, standard deviation, variance, or multi-step statistical
    calculations that would need several chained SQL queries.

    Do NOT use this for things plain SQL already handles well, like SUM,
    AVG, COUNT, GROUP BY, or simple filtering - use the SQL tools for those.

    The full sales data is already loaded as a pandas DataFrame called `df`.
    Write a short Python snippet using `df` and `pd` (pandas), and assign
    your final answer to a variable named `result`.

    Example input:
        result = df['discount'].corr(df['profit'])

    Example input:
        result = ((df[df['year'] == 2014]['sales'].sum()
                   - df[df['year'] == 2013]['sales'].sum())
                  / df[df['year'] == 2013]['sales'].sum()) * 100
    """
    df = _get_dataframe()
    local_vars = {"df": df, "pd": pd}
    try:
        exec(code, {"pd": pd}, local_vars)
        if "result" not in local_vars:
            return "Error: your code did not assign a value to a variable named `result`."
        return str(local_vars["result"])
    except Exception as e:
        return f"Error running pandas code: {e}"


@tool
def chart_generation_tool(code: str) -> str:
    """
    Use this tool when the user asks to see, plot, chart, graph, or visualize
    data - for example "show me a bar chart of sales by region" or "plot
    profit trend over the years".

    Do NOT use this tool if the user just wants a number or a text answer -
    only use it when a visual chart is explicitly requested or clearly implied.

    The full sales data is already loaded as a pandas DataFrame called `df`,
    and matplotlib.pyplot is available as `plt`. Write a short Python snippet
    that builds a chart using `df` and `plt`. Do NOT call plt.show() and do
    NOT call plt.savefig() yourself - saving happens automatically after your
    code runs.

    Example input:
        region_sales = df.groupby('region')['sales'].sum().sort_values(ascending=False)
        plt.figure(figsize=(10, 6))
        plt.bar(region_sales.index, region_sales.values)
        plt.xlabel('Region')
        plt.ylabel('Total Sales')
        plt.title('Total Sales by Region')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
    """
    global _last_chart_path
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend - no display needed, just saves files
    import matplotlib.pyplot as plt

    df = _get_dataframe()
    local_vars = {"df": df, "pd": pd, "plt": plt}
    try:
        plt.close("all")  # clear any leftover figures from previous calls
        exec(code, {"pd": pd, "plt": plt}, local_vars)

        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(CHARTS_DIR, filename)
        plt.savefig(filepath, bbox_inches="tight")
        plt.close("all")

        _last_chart_path = filepath  # so the Flask API can find this after invoke()
        return f"Chart saved successfully to: {filepath}"
    except Exception as e:
        return f"Error generating chart: {e}"


# Tracks the most recently generated chart file path, so the Flask API (app.py)
# can grab it after agent_executor.invoke() finishes, without parsing text.
_last_chart_path = None

def reset_last_chart():
    """Call this before agent_executor.invoke() so old chart paths don't leak
    into a new request that didn't actually generate a chart."""
    global _last_chart_path
    _last_chart_path = None

def get_last_chart_path():
    """Call this after agent_executor.invoke() to see if a chart was made."""
    return _last_chart_path


@tool
def report_generation_tool(code: str) -> str:
    """
    Use this tool when the user asks to export, download, or generate a
    report/spreadsheet/Excel file of data - for example "give me a report of
    sales by region and category", "export monthly sales as a spreadsheet",
    or "download a report of profit by segment with a chart".

    Do NOT use this for questions that just want a spoken/text answer. If the
    user ONLY wants a visual chart (no downloadable file), use
    chart_generation_tool instead.

    The full sales data is already loaded as a pandas DataFrame called `df`.
    Write a short Python snippet using `df` and `pd` that builds the report
    data, and assign the final pandas DataFrame (not a Series) to a variable
    named `report_df`. The FIRST column should be the category/label column
    (e.g. region, category, segment, year), and the remaining columns should
    be the numeric values.

    ONLY IF the user's question explicitly asks for a chart, graph, or visual
    inside the report (e.g. "with a chart", "including a graph"), ALSO set a
    variable named `include_chart = True`. If the user just asked for a plain
    report/spreadsheet with no mention of a chart, do NOT set this variable
    (it defaults to False, meaning a plain data-only spreadsheet is created).

    Example input (plain report, no chart):
        report_df = df.groupby('region')['sales'].sum().reset_index()

    Example input (report WITH a chart, only because the user asked for one):
        report_df = df.groupby('segment').agg(
            total_sales=('sales', 'sum'),
            total_profit=('profit', 'sum')
        ).reset_index()
        include_chart = True
    """
    global _last_report_path
    import openpyxl
    from openpyxl.chart import BarChart, Reference

    df = _get_dataframe()
    local_vars = {"df": df, "pd": pd}
    try:
        exec(code, {"pd": pd}, local_vars)
        if "report_df" not in local_vars:
            return "Error: your code did not assign a value to a variable named `report_df`."

        report_df = local_vars["report_df"]
        if not isinstance(report_df, pd.DataFrame):
            return "Error: `report_df` must be a pandas DataFrame, not a Series or other type."

        include_chart = bool(local_vars.get("include_chart", False))
        if include_chart and report_df.shape[1] < 2:
            return "Error: `report_df` needs at least 2 columns (a label column plus at least one numeric column) to include a chart."

        filename = f"report_{uuid.uuid4().hex[:8]}.xlsx"
        filepath = os.path.join(REPORTS_DIR, filename)

        # Write the data to a real Excel file
        report_df.to_excel(filepath, index=False, sheet_name="Report")

        if include_chart:
            # Re-open it with openpyxl to embed a native, editable Excel chart
            wb = openpyxl.load_workbook(filepath)
            ws = wb["Report"]

            n_rows = report_df.shape[0]
            n_cols = report_df.shape[1]

            chart = BarChart()
            chart.title = "Report Chart"
            chart.y_axis.title = report_df.columns[1]
            chart.x_axis.title = report_df.columns[0]

            # Data: all numeric columns (columns 2..n), including the header row for series names
            data = Reference(ws, min_col=2, max_col=n_cols, min_row=1, max_row=n_rows + 1)
            # Categories: the first column, excluding the header row
            categories = Reference(ws, min_col=1, max_col=1, min_row=2, max_row=n_rows + 1)

            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)
            chart.width = 18
            chart.height = 10

            # Place the chart a couple columns to the right of the data table
            anchor_cell = f"{chr(ord('A') + n_cols + 1)}2"
            ws.add_chart(chart, anchor_cell)

            wb.save(filepath)

        _last_report_path = filepath  # so the Flask API can find this after invoke()
        preview = report_df.head(5).to_string(index=False)
        chart_note = " (with an embedded chart)" if include_chart else ""
        return f"Report saved successfully to: {filepath}{chart_note}\n\nPreview:\n{preview}"
    except Exception as e:
        return f"Error generating report: {e}"


# Tracks the most recently generated report file path, same pattern as charts.
_last_report_path = None

def reset_last_report():
    global _last_report_path
    _last_report_path = None

def get_last_report_path():
    return _last_report_path


# ---- 4. Build the SQL agent, with the extra tools bolted on ----
# verbose=True prints the agent's reasoning steps and the SQL/code it generates,
# which is exactly the transparency we want for the "show your work" feature.
agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    agent_type="tool-calling",
    extra_tools=[pandas_calculation_tool, chart_generation_tool, report_generation_tool],
    verbose=True,
)

# ---- 5. Interactive loop ----
def main():
    print("=" * 80)
    print("AI Data Analyst Agent - ask me anything about your Sales data.")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 80)

    while True:
        question = input("\nYour question: ").strip()

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        print("-" * 80)
        try:
            result = agent_executor.invoke({"input": question})
            print("\nFINAL ANSWER:", result["output"])
        except Exception as e:
            print("ERROR while answering this question:", e)

if __name__ == "__main__":
    main()
