import os
import json
import time
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.state import AgentState
from agents.registry import get_registered_agents
from agents.coordinator_agent import coordinator_agent, router
from agents.planner_agent import planner_agent
from agents.research_agent import research_agent
from agents.tool_agent import tool_agent, analyze_file
from agents.code_agent import code_agent
from agents.review_agent import review_agent
from agents.critic_agent import critic_agent
from agents.memory_agent import memory_agent
from agents.summarizer_agent import summarizer_agent
from agents.chat_agent import chat_with_context
from session_store import (
    create_session, update_session, get_session,
    get_all_sessions, delete_session, append_message
)

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ── Graph ──────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner",     planner_agent)
    graph.add_node("coordinator", coordinator_agent)
    graph.add_node("research",    research_agent)
    graph.add_node("tool",        tool_agent)
    graph.add_node("code",        code_agent)
    graph.add_node("review",      review_agent)
    graph.add_node("critic",      critic_agent)
    graph.add_node("memory",      memory_agent)
    graph.add_node("summarizer",  summarizer_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "coordinator")

    for node in ["research", "tool", "code", "review", "critic", "memory"]:
        graph.add_edge(node, "coordinator")

    graph.add_conditional_edges("coordinator", router, {
        "research":   "research",
        "tool":       "tool",
        "code":       "code",
        "review":     "review",
        "critic":     "critic",
        "memory":     "memory",
        "summarizer": "summarizer",
        END:          END,
    })
    graph.add_edge("summarizer", END)
    return graph.compile()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agents", methods=["GET"])
def list_agents():
    agents = get_registered_agents()
    return jsonify({
        name: {"name": m["name"], "description": m["description"], "is_terminal": m["is_terminal"]}
        for name, m in agents.items()
    })


# ── File Analysis ──────────────────────────────────────────────────────────────

@app.route("/analyze-file", methods=["POST"])
def analyze_file_endpoint():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided."}), 400
        f = request.files["file"]
        if not f or not f.filename:
            return jsonify({"error": "Empty filename."}), 400
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in {".csv", ".xlsx", ".xls"}:
            return jsonify({"error": f"Unsupported type '{ext}'. Use CSV or Excel."}), 400
        file_bytes = f.read()
        if not file_bytes:
            return jsonify({"error": "Uploaded file is empty."}), 400

        print(f"[/analyze-file] {f.filename} ({len(file_bytes)} bytes)")
        result = analyze_file(file_bytes, f.filename)
        print(f"[/analyze-file] done. error={result.get('error')}")

        # ── Create a session so context-aware chat works immediately ────────
        sid = None
        if not result.get("error"):
            try:
                file_ctx = {
                    "file_analysis": {
                        "summary":  result.get("summary", ""),
                        "insights": result.get("insights", ""),
                        # chart_b64 intentionally excluded from session (too large)
                    }
                }
                # Use filename as the session title
                task_title = f"File analysis: {f.filename}"
                sid = create_session(task_title, file_ctx, [
                    {"role": "assistant",
                     "content": f"**File uploaded:** {f.filename}\n\n{result.get('insights', '')}",
                     "ts": time.time()}
                ])
                print(f"[/analyze-file] session created: {sid}")
            except Exception as se:
                print(f"[/analyze-file] session save failed: {se}")

        return jsonify({
            "filename":   f.filename,
            "summary":    result.get("summary", ""),
            "chart_b64":  result.get("chart_b64"),
            "insights":   result.get("insights", ""),
            "error":      result.get("error"),
            "session_id": sid,
        })
    except Exception as e:
        import traceback
        print(f"[/analyze-file] EXCEPTION:\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


# ── Agent Pipeline Run (streaming SSE) ────────────────────────────────────────

@app.route("/run", methods=["POST"])
def run():
    if request.content_type and "multipart/form-data" in request.content_type:
        task = (request.form.get("task") or "").strip()
        file_analysis_data = None
        if "file" in request.files:
            f = request.files["file"]
            if f and f.filename:
                file_analysis_data = analyze_file(f.read(), f.filename)
    else:
        data = request.get_json() or {}
        task = (data.get("task") or "").strip()
        file_analysis_data = None

    if not task:
        return jsonify({"error": "No task provided."}), 400

    def stream():
        graph = build_graph()
        initial_context = {}
        if file_analysis_data:
            initial_context["file_analysis"] = file_analysis_data

        initial_state: AgentState = {
            "task": task, "plan": [], "results": [],
            "context_dict": initial_context,
            "iterations": 0, "final_output": "", "next_agent": "",
        }

        final_context = {}
        final_output  = ""

        try:
            for step in graph.stream(initial_state):
                node_name = list(step.keys())[0]
                node_data = step[node_name]
                payload   = {"node": node_name, "data": {}}

                # Track context across all steps
                ctx = node_data.get("context_dict", {})
                if ctx:
                    final_context = ctx

                if node_name == "planner":
                    payload["data"]["plan"] = node_data.get("plan", [])

                elif node_name == "coordinator":
                    payload["data"]["next_agent"]      = node_data.get("next_agent", "")
                    payload["data"]["remaining_plan"]  = node_data.get("plan", [])

                elif node_name == "summarizer":
                    out = node_data.get("final_output", "")
                    if isinstance(out, dict):
                        from agents.summarizer_agent import _flatten_dict_to_markdown
                        out = _flatten_dict_to_markdown(out)
                    final_output = str(out)
                    payload["data"]["final_output"] = final_output
                    results = node_data.get("results", [])
                    if results:
                        payload["data"]["message"] = results[-1]

                    # ── Save session ───────────────────────────────────────
                    try:
                        sid = create_session(task, final_context, [
                            {"role": "assistant", "content": final_output, "ts": time.time()}
                        ])
                        payload["data"]["session_id"] = sid
                        print(f"[session] saved: {sid}")
                    except Exception as se:
                        print(f"[session] save failed: {se}")

                else:
                    results = node_data.get("results", [])
                    if results:
                        payload["data"]["message"] = results[-1]
                    if node_name in ctx:
                        raw = ctx[node_name]
                        payload["data"]["output"] = json.dumps(raw, indent=2) if isinstance(raw, dict) else raw
                    payload["data"]["context"] = {
                        k: (str(v)[:500] + "…" if len(str(v)) > 500 else v)
                        for k, v in ctx.items()
                        if k != "file_analysis"
                    }
                    payload["data"]["iterations"] = node_data.get("iterations", 0)

                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            import traceback
            print(f"[APP ERROR]\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'node':'error','data':{'message':str(e),'trace':traceback.format_exc()[-500:]}})}\n\n"

    return Response(stream(), mimetype="text/event-stream")


# ── Context-Aware Chat ─────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    """
    Follow-up chat using session context. Does NOT re-run agents.
    Body: { "session_id": "abc123", "message": "your question" }
    """
    try:
        data       = request.get_json() or {}
        sid        = (data.get("session_id") or "").strip()
        message    = (data.get("message") or "").strip()

        if not message:
            return jsonify({"error": "No message provided."}), 400

        # Load context — graceful fallback if no session
        context_dict = {}
        history      = []
        if sid:
            session = get_session(sid)
            if session:
                context_dict = session.get("context_dict", {})
                history      = session.get("messages", [])
            else:
                return jsonify({"error": f"Session '{sid}' not found."}), 404

        # Generate answer
        answer = chat_with_context(message, context_dict, history)

        # Persist the exchange
        if sid:
            append_message(sid, "user",      message)
            append_message(sid, "assistant", answer)

        return jsonify({"response": answer, "session_id": sid})

    except Exception as e:
        import traceback
        print(f"[/chat] ERROR:\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


# ── Session Management ─────────────────────────────────────────────────────────

@app.route("/sessions", methods=["GET"])
def list_sessions():
    sessions = get_all_sessions()
    return jsonify([{
        "id":      s["id"],
        "title":   s.get("title", "Untitled"),
        "created": s.get("created", 0),
        "updated": s.get("updated", s.get("created", 0)),
        "msg_count": len(s.get("messages", [])),
    } for s in sessions])


@app.route("/sessions/<sid>", methods=["GET"])
def load_session(sid):
    session = get_session(sid)
    if not session:
        return jsonify({"error": "Session not found."}), 404
    # Strip chart_b64 to keep payload manageable
    ctx = dict(session.get("context_dict", {}))
    fa  = ctx.get("file_analysis", {})
    if fa:
        fa = dict(fa); fa.pop("chart_b64", None)
        ctx["file_analysis"] = fa
    return jsonify({
        "id":           session["id"],
        "title":        session.get("title", ""),
        "task":         session.get("task", ""),
        "created":      session.get("created", 0),
        "updated":      session.get("updated", 0),
        "context_dict": ctx,
        "messages":     session.get("messages", []),
    })


@app.route("/sessions/<sid>", methods=["DELETE"])
def remove_session(sid):
    delete_session(sid)
    return jsonify({"ok": True})


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Nexus Multi-Agent AI...")
    print(f"Registered agents: {list(get_registered_agents().keys())}")
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)
