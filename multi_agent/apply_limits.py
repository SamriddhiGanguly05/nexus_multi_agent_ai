import os
import glob
import re

limits = {
    'planner_agent.py': 200,
    'research_agent.py': 600,
    'tool_agent.py': 400,
    'code_agent.py': 1000,
    'review_agent.py': 500,
    'critic_agent.py': 500,
    'memory_agent.py': 300,
    'summarizer_agent.py': 1000,
    'coordinator_agent.py': 100 # usually just graphs, but just in case
}

agent_files = glob.glob(r"c:\Users\dream\Desktop\multi_agent\multi_agent\agents\*_agent.py")
for file in agent_files:
    filename = os.path.basename(file)
    limit = limits.get(filename, 500)
    
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = re.sub(
        r'llm = ChatGroq\(model="[^"]+", api_key=os\.getenv\("GROQ_API_KEY"\)[^\)]*\)',
        f'llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), max_tokens={limit})',
        content
    )
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Updated all agents to llama-3.1-8b-instant with dynamic TPM limits successfully.")
