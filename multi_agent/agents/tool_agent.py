from langchain_groq import ChatGroq
import os
import io
import base64
import asyncio
import sys

from dotenv import load_dotenv
from agents.state import AgentState
from agents.registry import register_agent
from agents.json_utils import invoke_with_json_retry

# ✅ MCP IMPORTS
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

# ── Matplotlib backend ─────────────────────────────────────────
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=800,
    temperature=0.3
)

# ───────────────────────────────────────────────────────────────
# ✅ MCP CONNECTION HELPERS (FINAL WORKING VERSION)
# ───────────────────────────────────────────────────────────────

def get_mcp_tools_sync():
    async def _fetch():
        client = MultiServerMCPClient(
            {
                "nexus-tools": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_tools.server"],  # ✅ FIXED
                    "transport": "stdio",
                }
            }
        )

        async with client.session("nexus-tools") as session:
            tools = await load_mcp_tools(session)
            print(f"[MCP] Tools loaded: {[t.name for t in tools]}")
            return tools

    return asyncio.run(_fetch())


def call_mcp_tool_sync(tool_name: str, kwargs: dict) -> str:
    async def _call():
        client = MultiServerMCPClient(
            {
                "nexus-tools": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_tools.server"],  # ✅ FIXED
                    "transport": "stdio",
                }
            }
        )

        async with client.session("nexus-tools") as session:
            tools = await load_mcp_tools(session)
            tool_map = {t.name: t for t in tools}

            if tool_name not in tool_map:
                return f"Tool '{tool_name}' not found."

            print(f"[MCP] Executing tool: {tool_name} with {kwargs}")

            result = await tool_map[tool_name].ainvoke(kwargs)

            print(f"[MCP] Result: {result}")

            return str(result)

    return asyncio.run(_call())

# ───────────────────────────────────────────────────────────────
# FILE ANALYSIS FUNCTIONS
# ───────────────────────────────────────────────────────────────

def load_csv(file_path_or_bytes, filename="uploaded_file"):
    if isinstance(file_path_or_bytes, (str, os.PathLike)):
        if str(file_path_or_bytes).lower().endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path_or_bytes)
        return pd.read_csv(file_path_or_bytes)
    else:
        buf = io.BytesIO(file_path_or_bytes)
        if filename.lower().endswith(('.xlsx', '.xls')):
            return pd.read_excel(buf)
        return pd.read_csv(buf)


def summarize_data(df) -> str:
    try:
        lines = []
        lines.append(f"**Shape:** {df.shape[0]} rows × {df.shape[1]} columns")
        lines.append(f"**Columns:** {', '.join(df.columns.tolist())}")
        lines.append("")

        null_counts = df.isnull().sum()
        null_info = null_counts[null_counts > 0]

        if not null_info.empty:
            lines.append("**Missing Values:**")
            for col, cnt in null_info.items():
                pct = round(cnt / len(df) * 100, 1)
                lines.append(f"  - `{col}`: {cnt} ({pct}%)")
        else:
            lines.append("**Missing Values:** None ✅")

        lines.append("\n**Numeric Summary:**")

        numeric_df = df.select_dtypes(include='number')
        if not numeric_df.empty:
            desc = numeric_df.describe().round(2)
            for col in desc.columns:
                lines.append(
                    f"  - `{col}`: mean={desc[col]['mean']}, "
                    f"min={desc[col]['min']}, max={desc[col]['max']}"
                )
        else:
            lines.append("  - No numeric columns found.")

        return "\n".join(lines)
    except Exception as e:
        return str(e)


def plot_data(df) -> str:
    try:
        numeric_df = df.select_dtypes(include='number')
        if numeric_df.empty:
            return None

        fig, ax = plt.subplots()
        numeric_df.hist(ax=ax)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)

        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        print(e)
        return None


def analyze_file(file_bytes: bytes, filename: str) -> dict:
    result = {"summary": "", "chart_b64": None, "insights": "", "error": None}

    try:
        df = load_csv(file_bytes, filename)
        result["summary"] = summarize_data(df)
        result["chart_b64"] = plot_data(df)

        prompt = f"""
Give 3 insights from this dataset:

{result['summary']}

Return JSON:
{{
 "thought_process": "...",
 "status": "success",
 "output_data": "..."
}}
"""
        parsed = invoke_with_json_retry(llm, prompt)
        result["insights"] = parsed.get("output_data", "")

    except Exception as e:
        result["error"] = str(e)

    return result

# ───────────────────────────────────────────────────────────────
# TOOL AGENT
# ───────────────────────────────────────────────────────────────

@register_agent("tool", "Fetches real live data via MCP tools.")
def tool_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})

    # FILE ANALYSIS
    file_analysis = context_dict.get("file_analysis", None)
    if file_analysis:
        context_dict["tool"] = (
            f"**File Analysis Results:**\n\n"
            f"{file_analysis.get('summary', '')}\n\n"
            f"**AI Insights:**\n{file_analysis.get('insights', '')}"
        )
        results = state.get("results", [])
        results.append("[tool] file analysis completed")
        return {"results": results, "context_dict": context_dict}

    # MCP TOOL DISCOVERY
    try:
        lc_tools = get_mcp_tools_sync()
        available_tools = "\n".join(
            f"- {t.name}: {t.description}" for t in lc_tools
        )
    except Exception as e:
        available_tools = "search_web, get_crypto_price, get_weather"
        print(f"[tool_agent] MCP failed: {e}")

    research_context = context_dict.get("research", "")

    prompt = f"""
You are a Tool Execution Agent.

Task: {task}
Context: {research_context}

Available Tools:
{available_tools}

Respond ONLY in JSON:
{{
 "thought_process": "...",
 "status": "success",
 "output_data": [
   {{"tool_name": "...", "kwargs": {{}}}}
 ]
}}
"""

    parsed = invoke_with_json_retry(llm, prompt)

    tool_requests = parsed.get("output_data", [])
    execution_logs = []

    for req in tool_requests:
        if isinstance(req, dict) and "tool_name" in req:
            result = call_mcp_tool_sync(
                req["tool_name"],
                req.get("kwargs", {})
            )
            execution_logs.append(f"[{req['tool_name']}] → {result}")

    if not execution_logs:
        execution_logs.append("No MCP tool executed.")

    context_dict["tool"] = "\n".join(execution_logs)

    results = state.get("results", [])
    results.append("[tool] completed")

    return {"results": results, "context_dict": context_dict}