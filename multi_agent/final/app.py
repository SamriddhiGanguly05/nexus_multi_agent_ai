import os
import json
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.state import AgentState
from agents.registry import get_registered_agents
from agents.coordinator_agent import coordinator_agent, router
from agents.planner_agent import planner_agent
from agents.research_agent import research_agent
from agents.tool_agent import tool_agent
from agents.code_agent import code_agent
from agents.review_agent import review_agent
from agents.critic_agent import critic_agent
from agents.memory_agent import memory_agent
from agents.summarizer_agent import summarizer_agent

load_dotenv()
app = Flask(__name__)


def build_graph():
    """
    Builds the LangGraph agent workflow.
    Routing is dynamic — coordinator reads the plan and routes to the correct agent.
    No hardcoded agent sequences.
    """
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("planner", planner_agent)
    graph.add_node("coordinator", coordinator_agent)
    graph.add_node("research", research_agent)
    graph.add_node("tool", tool_agent)
    graph.add_node("code", code_agent)
    graph.add_node("review", review_agent)
    graph.add_node("critic", critic_agent)
    graph.add_node("memory", memory_agent)
    graph.add_node("summarizer", summarizer_agent)

    # Entry point
    graph.set_entry_point("planner")

    # Planner always goes to coordinator
    graph.add_edge("planner", "coordinator")

    # All agent nodes go back to coordinator (which pops the next step from plan)
    # except summarizer which is terminal
    all_agent_nodes = ["research", "tool", "code", "review", "critic", "memory"]
    for node in all_agent_nodes:
        graph.add_edge(node, "coordinator")

    # Coordinator dynamically routes to whichever agent is next in the plan
    route_map = {
        "research":   "research",
        "tool":       "tool",
        "code":       "code",
        "review":     "review",
        "critic":     "critic",
        "memory":     "memory",
        "summarizer": "summarizer",
        END:          END,
    }
    graph.add_conditional_edges("coordinator", router, route_map)

    # Summarizer is the terminal node
    graph.add_edge("summarizer", END)

    return graph.compile()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agents", methods=["GET"])
def list_agents():
    """Expose registered agents — demonstrates MCP capability discovery."""
    agents = get_registered_agents()
    return jsonify({
        name: {
            "name": meta["name"],
            "description": meta["description"],
            "is_terminal": meta["is_terminal"]
        }
        for name, meta in agents.items()
    })


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json()
    task = (data.get("task") or "").strip()

    if not task:
        return jsonify({"error": "No task provided."}), 400

    def stream():
        graph = build_graph()
        initial_state: AgentState = {
            "task": task,
            "plan": [],
            "results": [],
            "context_dict": {},
            "iterations": 0,
            "final_output": "",
            "next_agent": ""
        }

        try:
            for step in graph.stream(initial_state):
                node_name = list(step.keys())[0]
                node_data = step[node_name]

                # Build a clean payload for the UI
                payload = {"node": node_name, "data": {}}

                if node_name == "planner":
                    payload["data"]["plan"] = node_data.get("plan", [])

                elif node_name == "coordinator":
                    payload["data"]["next_agent"] = node_data.get("next_agent", "")
                    payload["data"]["remaining_plan"] = node_data.get("plan", [])

                elif node_name == "summarizer":
                    payload["data"]["final_output"] = node_data.get("final_output", "")

                else:
                    results = node_data.get("results", [])
                    if results:
                        payload["data"]["message"] = results[-1]
                    # Send latest context output for this agent
                    ctx = node_data.get("context_dict", {})
                    if node_name in ctx:
                        raw = str(ctx[node_name])
                        payload["data"]["output"] = raw[:1000] + ("..." if len(raw) > 1000 else "")

                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            import traceback
            error_payload = {
                "node": "error",
                "data": {
                    "message": str(e),
                    "trace": traceback.format_exc()[-500:]
                }
            }
            print(f"[APP ERROR] {traceback.format_exc()}")
            yield f"data: {json.dumps(error_payload)}\n\n"

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Starting Nexus Multi-Agent AI...")
    print(f"Registered agents: {list(get_registered_agents().keys())}")
    app.run(debug=True, port=5000, threaded=True)
