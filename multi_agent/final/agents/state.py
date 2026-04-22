from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    task: str
    plan: List[str]
    results: List[str]
    context_dict: Dict[str, Any]
    iterations: int
    final_output: str
    next_agent: str
