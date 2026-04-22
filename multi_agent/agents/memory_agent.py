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


@register_agent("memory", "Extracts key takeaways and reusable patterns. Simulates vector DB storage.")
def memory_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})
    code = context_dict.get("code", "")
    critic_feedback = context_dict.get("critic_feedback", "")
    review = context_dict.get("review", "")

    prompt = f"""
You are the Memory Agent in a multi-agent AI pipeline.

Original Task: {task}
Final Code Output: {code}
Critic Improvements Applied: {critic_feedback}
Review Notes: {review}

Extract exactly 3 core takeaways and reusable patterns from this execution.
Format your output as a simulated Vector DB payload:

VECTOR DB PAYLOAD:
[Entry 1] Pattern: <name> | Embedding Key: <key> | Value: <summary>
[Entry 2] Pattern: <name> | Embedding Key: <key> | Value: <summary>
[Entry 3] Pattern: <name> | Embedding Key: <key> | Value: <summary>

{enforce_output_schema()}
Put the full Vector DB payload in output_data as a string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    context_dict["memory"] = parsed.get("output_data", "No memory output.")

    results = state.get("results", [])
    results.append("[memory] completed")

    return {"results": results, "context_dict": context_dict}
