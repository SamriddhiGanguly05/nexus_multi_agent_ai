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
    max_tokens=1800,
    temperature=0.4
)


@register_agent("summarizer", "Final agent — synthesizes all outputs into a complete, formatted response.", is_terminal=True)
def summarizer_agent(state: AgentState) -> dict:
    context_dict = state.get("context_dict", {})
    original_task = state.get("task", "")

    # Build a trimmed summary of context to avoid token overflow
    context_summary = {}
    for key in ["research", "tool", "code", "review", "critic_feedback", "memory"]:
        val = context_dict.get(key, "")
        context_summary[key] = str(val)[:800] if val else "Not available."

    prompt = f"""
You are the Master Synthesizer — the final agent in a multi-agent AI pipeline.

Original Task: {original_task}

Outputs from all agents:
- Research: {context_summary['research']}
- Tool Execution Log: {context_summary['tool']}
- Generated Code: {context_summary['code']}
- Code Review: {context_summary['review']}
- Critic Improvements: {context_summary['critic_feedback']}
- Memory / Patterns: {context_summary['memory']}

Synthesize all of the above into a final, well-formatted Markdown report covering:
## 1. Executive Summary
## 2. Research Findings & APIs Used
## 3. Final Code (with improvements from critic noted)
## 4. Key Patterns Learned
## 5. Next Steps

{enforce_output_schema()}
Put the complete Markdown report in output_data as a string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=4)

    results = state.get("results", [])
    results.append("[summarizer] completed")

    return {
        "final_output": parsed.get("output_data", "Summarizer produced no output."),
        "results": results
    }
