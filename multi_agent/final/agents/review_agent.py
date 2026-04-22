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
    temperature=0.3
)


@register_agent("review", "Reviews code and output for QA, completeness, correctness, and security.")
def review_agent(state: AgentState) -> dict:
    context_dict = state.get("context_dict", {})
    code = context_dict.get("code", "No code available to review.")

    prompt = f"""
You are the QA Review Agent in a multi-agent AI pipeline.

Code to Review:
{code}

Perform a thorough code review checking:
1. Exception handling — are errors caught gracefully?
2. Variable correctness — are types and values appropriate?
3. Security posture — any injection risks, hardcoded secrets, or unsafe operations?
4. Logic correctness — does the code actually solve the task?
5. Completeness — are there any missing pieces or stubs?

{enforce_output_schema()}
Put your detailed review notes in output_data as a structured string with numbered findings.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=4)
    context_dict["review"] = parsed.get("output_data", "No review output.")

    results = state.get("results", [])
    results.append("[review] completed")

    return {"results": results, "context_dict": context_dict}
