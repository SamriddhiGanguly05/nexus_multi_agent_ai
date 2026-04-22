from langgraph.graph import END
from agents.state import AgentState
from agents.registry import get_registered_agents
from dotenv import load_dotenv
load_dotenv()


def trim_context_dict(context_dict: dict, max_chars: int = 2000) -> dict:
    """Trim each context value to avoid token overflows in downstream agents."""
    trimmed = {}
    for k, v in context_dict.items():
        trimmed[k] = str(v)[:max_chars]
    return trimmed


def coordinator_agent(state: AgentState) -> dict:
    """
    A2A Coordinator: reads the plan, picks the next agent,
    advances the plan queue, and trims context for efficiency.
    """
    plan = state.get("plan", [])

    if not plan:
        return {
            "next_agent": "END",
            "results": state.get("results", []) + ["[Coordinator] Plan exhausted — routing to END."]
        }

    next_up = plan[0]
    new_plan = plan[1:]

    raw_dict = state.get("context_dict", {})
    optimized_context = trim_context_dict(raw_dict, max_chars=2000)

    results = state.get("results", [])
    results.append(f"[Coordinator] Next agent → {next_up} | Remaining plan: {new_plan}")

    return {
        "plan": new_plan,
        "next_agent": next_up,
        "results": results,
        "context_dict": optimized_context
    }


def router(state: AgentState):
    """
    Dynamic router — reads next_agent from state and maps to the correct graph node.
    Never hardcoded: works with whatever agents are registered.
    """
    next_a = state.get("next_agent", "END")

    if not next_a or next_a == "END":
        return "summarizer"

    agents = get_registered_agents()

    if next_a in agents:
        return next_a

    # Fuzzy match — handles cases where LLM returns 'code_agent' instead of 'code'
    for name in agents:
        if name in next_a or next_a in name:
            print(f"[Router] Fuzzy matched '{next_a}' → '{name}'")
            return name

    print(f"[Router] Unknown agent '{next_a}' — falling back to summarizer.")
    return "summarizer"
