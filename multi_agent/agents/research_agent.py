import re
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from agents.state import AgentState
from agents.registry import register_agent
from agents.json_utils import invoke_with_json_retry, enforce_output_schema

load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=800,
    temperature=0.3
)

# ── Strip ALL URLs unconditionally ───────────────────────────────────────────
_URL_RE = re.compile(r'https?://\S+')


def sanitize_research_output(text: str) -> str:
    """Remove every URL from research output — no links allowed."""
    if not isinstance(text, str):
        return text
    # Replace any http/https URL with nothing (clean removal)
    cleaned = _URL_RE.sub('', text)
    # Also strip leftover markdown link syntax [text](url) → just text
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', cleaned)
    return cleaned


# ── Agent ─────────────────────────────────────────────────────────────────────

@register_agent("research", "Searches for external information, concrete datasets, and technical sources.")
def research_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})
    planner_context = context_dict.get("planner", "")

    prompt = f"""
You are the Research Agent in a multi-agent AI pipeline.

Task: {task}
Planner Context: {planner_context}

Provide structured research including:
1. Key facts relevant to the task
2. Technical considerations and known challenges
3. Recommended approach or architecture

NO LINKS RULE — ABSOLUTE:
- Do NOT include any URLs, hyperlinks, or web addresses whatsoever.
- Do NOT write http, https, www, or any domain names.
- Instead: name the dataset/tool/library, name the organisation, describe what it contains.
- Example of CORRECT format: "The UCI Heart Disease dataset (available from the UCI ML Repository) contains 303 patient records with 14 attributes including age, cholesterol, and heart rate."
- Example of WRONG format: "https://archive.ics.uci.edu/ml/datasets/heart+disease"
- Pretend hyperlinks do not exist. Text descriptions only.

{enforce_output_schema()}
Put your research in output_data as a well-structured Markdown string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    raw_output = parsed.get("output_data", "No research output.")

    # Post-process: strip any URLs that slipped through and aren't whitelisted
    if isinstance(raw_output, str):
        raw_output = sanitize_research_output(raw_output)

    context_dict["research"] = raw_output
    results = state.get("results", [])
    results.append("[research] completed")

    return {"results": results, "context_dict": context_dict}
