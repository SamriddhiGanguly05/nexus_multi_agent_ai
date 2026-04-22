"""
chat_agent.py — Context-aware follow-up chat using retained pipeline context.
Does NOT re-run the full agent pipeline. Answers questions using stored context.
"""
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from agents.json_utils import invoke_with_json_retry

load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=700,
    temperature=0.4,
)


def chat_with_context(question: str, context_dict: dict, history: list) -> str:
    """
    Answer a follow-up question using the retained context from previous agent runs.

    Args:
        question:     The user's new question.
        context_dict: The full context_dict saved from the pipeline run.
        history:      List of {role, content} dicts (recent chat turns).

    Returns:
        A Markdown-formatted string answer.
    """
    # ── Build trimmed context snippets ────────────────────────────────────────
    research   = str(context_dict.get("research", ""))[:600]
    code       = str(context_dict.get("code", ""))[:700]
    tool_out   = str(context_dict.get("tool", ""))[:400]
    review     = str(context_dict.get("review", ""))[:300]
    final_out  = str(context_dict.get("final_output", ""))[:500]

    file_analysis = context_dict.get("file_analysis", {}) or {}
    file_summary  = str(file_analysis.get("summary", ""))[:600]
    file_insights = str(file_analysis.get("insights", ""))[:400]

    # ── Last 6 history turns ───────────────────────────────────────────────────
    history_str = ""
    for msg in (history or [])[-6:]:
        role    = msg.get("role", "user").upper()
        content = str(msg.get("content", ""))[:300]
        history_str += f"\n[{role}]: {content}"

    has_file = bool(file_summary)
    context_note = (
        "The user uploaded a dataset. Prioritise the file summary and insights "
        "when answering questions about the data."
        if has_file else
        "No file was uploaded. Answer using the agent pipeline outputs."
    )

    prompt = f"""
You are a helpful, context-aware AI assistant.
{context_note}

=== RETAINED CONTEXT ===
Research: {research or 'N/A'}
Code Generated: {code or 'N/A'}
Tool Output: {tool_out or 'N/A'}
Code Review: {review or 'N/A'}
Final Summary: {final_out or 'N/A'}
File Dataset Summary: {file_summary or 'N/A'}
File Insights: {file_insights or 'N/A'}

=== CONVERSATION HISTORY ===
{history_str or '(No prior messages)'}

=== NEW QUESTION ===
{question}

RULES:
- Answer in clean Markdown (bullets, bold, code blocks where useful).
- Maximum 250 words.
- Stay grounded in the context above.
- If the question is unrelated, say so briefly and offer to help with the context.
- Do NOT make up data not present in the context.

Respond as valid JSON only:
{{
  "thought_process": "brief",
  "status": "success",
  "output_data": "your markdown answer here"
}}
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    answer = parsed.get("output_data", "")
    if not answer or not str(answer).strip():
        answer = "_Sorry, I couldn't generate a response. Please try rephrasing._"
    return str(answer)
