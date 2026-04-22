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


@register_agent("review", "Reviews code and output for QA, completeness, correctness, and security.")
def review_agent(state: AgentState) -> dict:
    context_dict = state.get("context_dict", {})
    code = context_dict.get("code", "No code available to review.")

    prompt = f"""
You are the QA Review Agent in a multi-agent AI pipeline.

Task: {state.get('task', 'Unknown')}

Code to Review:
{code}

Perform a thorough code review checking:
1. Edge cases - are tricky inputs and fringe scenarios handled?
2. Time complexity - are the algorithms reasonably efficient?
3. Logical correctness vs task - does the code actually solve the original user task?
4. Exception handling - are errors caught gracefully?
5. Variables and security - any injection risks, hardcoded secrets, or type issues?

You MUST return at least 3 concrete issues.

{enforce_output_schema()}
Put your detailed review notes in output_data as a structured string with numbered findings.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    context_dict["review"] = parsed.get("output_data", "No review output.")

    results = state.get("results", [])
    results.append("[review] completed")

    return {"results": results, "context_dict": context_dict}
