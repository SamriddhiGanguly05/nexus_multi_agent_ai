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
    max_tokens=1200,
    temperature=0.2
)

MAX_CODE_LINES = 150


def enforce_code_length(code_str: str) -> str:
    """If code exceeds MAX_CODE_LINES, replace with a structured summary."""
    lines = code_str.strip().splitlines()
    if len(lines) <= MAX_CODE_LINES:
        return code_str
    # Summarize: keep first 50 lines + last 20 lines with a note
    head = lines[:50]
    tail = lines[-20:]
    summary_note = [
        "",
        f"# ── [Code truncated: {len(lines)} lines → showing head + tail] ──",
        f"# Full logic: {len(lines)} lines covering the full implementation.",
        f"# Key sections below — download or request full code if needed.",
        "# ...",
        ""
    ]
    return "\n".join(head + summary_note + tail)


@register_agent("code", "Generates complete, executable code taking all context into account.")
def code_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})

    research = context_dict.get("research", "")
    tool = context_dict.get("tool", "")
    
    critic_feedback_raw = context_dict.get("critic_feedback", {})
    if isinstance(critic_feedback_raw, dict):
        critic_feedback = str(critic_feedback_raw.get("issues", "None yet"))
    else:
        critic_feedback = str(critic_feedback_raw)

    previous_code = context_dict.get("code", "")
    if previous_code and previous_code != "No code available." and previous_code != "No code output.":
        context_dict["code_previous"] = previous_code

    prompt = f"""
You are the elite Code Agent in a multi-agent AI pipeline.

Task: {task}
Research Context: {research}
Tool Execution Traces: {tool}
Critic Feedback to Apply: {critic_feedback if critic_feedback and critic_feedback != "None yet" else "None yet — this is the first pass."}

Write complete, executable, well-commented Python code for this task.
Requirements:
- Include proper imports
- Add docstrings to all functions
- Handle exceptions with try/except
- No placeholder stubs or 'pass' statements — fully implement everything
- Use realistic variable names and modular structure
- You MUST incorporate all critic feedback. If no changes are made, explain why.
- Do NOT repeat the exact same code if feedback was provided.

CODE LENGTH RULES (CRITICAL):
- Keep code under 150 lines total.
- If the full implementation would exceed 150 lines, write the CORE logic only.
- Omit boilerplate, excessive comments, and repeated patterns.
- Add a brief comment at the top listing what was omitted for brevity.

{enforce_output_schema()}
Put the complete Python code in output_data as a string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    new_code = parsed.get("output_data", "No code output.")
    if isinstance(new_code, str):
        new_code = enforce_code_length(new_code)
    context_dict["code"] = new_code

    results = state.get("results", [])
    if previous_code and previous_code == new_code:
        print("[WARNING] No improvement detected in code generation.")
        results.append("[code] WARNING: No improvement detected")
    else:
        results.append("[code] completed")

    return {"results": results, "context_dict": context_dict}
