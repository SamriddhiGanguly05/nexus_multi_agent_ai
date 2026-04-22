from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from agents.state import AgentState
from agents.registry import get_registered_agents, register_agent
from agents.json_utils import invoke_with_json_retry, enforce_output_schema
load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=800,
    temperature=0.3
)

DEFAULT_PLAN = ["research", "tool", "code", "review", "critic", "memory", "summarizer"]


@register_agent("planner", "Plans the full execution pipeline dynamically based on the task.")
def planner_agent(state: AgentState) -> dict:
    agents = get_registered_agents()

    # Build agent descriptions excluding planner itself
    agent_descriptions = [
        f"- {name}: {meta['description']}"
        for name, meta in agents.items()
        if name != "planner"
    ]
    descriptions_str = "\n".join(agent_descriptions)

    prompt = f"""
You are the Master Planner Agent in a multi-agent AI pipeline.

Task: {state['task']}

AVAILABLE AGENTS (use only these exact names):
{descriptions_str}

YOUR JOB:
Decide the best sequence of agents to complete this task end-to-end. Choose ONLY the agents truly needed for the given task. Do NOT include all agents if the task is simple.

STRICT RULES:
1. "summarizer" must be LAST - always
2. "memory" must come directly before "summarizer" if you decide to include it (it is recommended for storing context).
3. Do NOT include "planner" in the plan
4. Choose the minimal but effective set of agents.
5. output_data must be a JSON ARRAY of agent name strings

{enforce_output_schema()}
Example of correct output_data: ["research", "code", "memory", "summarizer"]
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2, fallback_key="output_data")
    out_data = parsed.get("output_data", [])

    # Handle case where LLM returned a string instead of array
    if isinstance(out_data, str):
        import json, re
        try:
            arr = json.loads(out_data)
            if isinstance(arr, list):
                out_data = arr
            else:
                out_data = []
        except Exception:
            # Try to extract array from string
            match = re.search(r'\[.*?\]', out_data, re.DOTALL)
            out_data = json.loads(match.group()) if match else []

    # Clean and validate plan - only keep known agent names, skip planner
    valid_names = set(agents.keys()) - {"planner"}
    clean_plan = []
    seen = set()
    for step in out_data:
        step_str = str(step).strip().lower()
        if step_str in valid_names and step_str not in seen:
            clean_plan.append(step_str)
            seen.add(step_str)

    # Enforce summarizer is last
    if "summarizer" in clean_plan:
        clean_plan = [s for s in clean_plan if s != "summarizer"]
    clean_plan.append("summarizer")

    # If planner returned garbage, use the safe default
    if len(clean_plan) < 2:
        print("[Planner] Plan too short - using default plan.")
        clean_plan = ["code", "summarizer"]

    print(f"[Planner] Final plan: {clean_plan}")

    context_dict = state.get("context_dict", {})
    context_dict["planner"] = clean_plan

    results = state.get("results", [])
    results.append(f"[planner] Plan created: {clean_plan}")

    return {
        "plan": clean_plan,
        "next_agent": "coordinator",
        "context_dict": context_dict,
        "results": results
    }
