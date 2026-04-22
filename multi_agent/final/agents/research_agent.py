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
    temperature=0.4
)


@register_agent("research", "Searches for external information, concrete datasets, and technical sources.")
def research_agent(state: AgentState) -> dict:
    task = state["task"]
    context_dict = state.get("context_dict", {})
    planner_context = context_dict.get("planner", "")

    prompt = f"""
You are the elite Research Agent in a multi-agent AI pipeline.

Task: {task}
Planner Context: {planner_context}

Provide exhaustive, structured research including:
1. Key concrete facts relevant to the task
2. Technical considerations and known challenges
3. Relevant mock API/dataset references that would be useful
4. Recommended approach or architecture

{enforce_output_schema()}
Put your complete research findings in output_data as a well-structured string.
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=4)
    context_dict["research"] = parsed.get("output_data", "No research output.")

    results = state.get("results", [])
    results.append("[research] completed")

    return {"results": results, "context_dict": context_dict}
