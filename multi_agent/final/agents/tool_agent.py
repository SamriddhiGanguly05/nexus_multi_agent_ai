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


@register_agent("tool", "Simulates fetching APIs, querying DBs, and executing external capabilities.")
def tool_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})
    research_context = context_dict.get("research", "No research context available.")

    prompt = f"""
You are the Tool Execution Agent in a multi-agent AI pipeline.

Task: {task}
Research Context: {research_context}

Simulate the MCP tool calls that would be needed for this task.
Format your output_data as a structured execution log like:

[TOOL CALL 1] GET https://api.example.com/endpoint
[PARAMS] {{"key": "value"}}
[RESPONSE] {{"status": 200, "data": {{...}}}}

[TOOL CALL 2] POST https://api.example.com/other
...

Make the mock API responses realistic and relevant to the task.

{enforce_output_schema()}
Put the full execution log in output_data as a string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=4)
    context_dict["tool"] = parsed.get("output_data", "No tool output.")

    results = state.get("results", [])
    results.append("[tool] completed")

    return {"results": results, "context_dict": context_dict}
