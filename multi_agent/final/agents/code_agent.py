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
    max_tokens=1500,
    temperature=0.2
)


@register_agent("code", "Generates complete, executable code taking all context into account.")
def code_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})

    research = context_dict.get("research", "")
    tool = context_dict.get("tool", "")
    critic_feedback = context_dict.get("critic_feedback", "")

    prompt = f"""
You are the elite Code Agent in a multi-agent AI pipeline.

Task: {task}
Research Context: {research}
Tool Execution Traces: {tool}
Critic Feedback to Apply: {critic_feedback if critic_feedback else "None yet — this is the first pass."}

Write complete, executable, well-commented Python code for this task.
Requirements:
- Include proper imports
- Add docstrings to all functions
- Handle exceptions with try/except
- No placeholder stubs or 'pass' statements — fully implement everything
- Use realistic variable names and modular structure

{enforce_output_schema()}
Put the complete Python code in output_data as a string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=4)
    context_dict["code"] = parsed.get("output_data", "No code output.")

    results = state.get("results", [])
    results.append("[code] completed")

    return {"results": results, "context_dict": context_dict}
