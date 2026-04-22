import os

BASE = "multi_agent"

folders = [
    f"{BASE}/agents",
    f"{BASE}/mcp_tools",
    f"{BASE}/templates",
]

files = {
    f"{BASE}/agents/__init__.py": "",
    f"{BASE}/agents/orchestrator.py": "# Orchestrator agent - plans and delegates tasks\n",
    f"{BASE}/agents/research_agent.py": "# Research agent - searches and fetches information\n",
    f"{BASE}/agents/code_agent.py": "# Code agent - writes and explains code\n",
    f"{BASE}/agents/summarizer_agent.py": "# Summarizer agent - compiles and summarizes results\n",
    f"{BASE}/mcp_tools/__init__.py": "",
    f"{BASE}/mcp_tools/tools.py": "# MCP tool definitions\n",
    f"{BASE}/templates/index.html": "<!-- Flask UI -->\n",
    f"{BASE}/app.py": "# Flask server - entry point\n",
    f"{BASE}/requirements.txt": (
        "langgraph\n"
        "langchain-groq\n"
        "langchain-community\n"
        "langchain-mcp-adapters\n"
        "flask\n"
        "requests\n"
    ),
}

for folder in folders:
    os.makedirs(folder, exist_ok=True)
    print(f"created folder → {folder}")

for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)
    print(f"created file  → {path}")

print("\n✅ multi_agent project structure ready!")
print("Next: cd multi_agent && pip install -r requirements.txt")