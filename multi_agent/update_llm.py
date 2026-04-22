import os
import glob
import re

agent_files = glob.glob(r"c:\Users\dream\Desktop\multi_agent\multi_agent\agents\*_agent.py")
for file in agent_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace the previous LLM definition with a heavily restricted token count to prevent TPM 413 error
    content = re.sub(
        r'llm = ChatGroq\(model="[^"]+", api_key=os\.getenv\("GROQ_API_KEY"\)[^\)]*\)',
        'llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), max_tokens=300)',
        content
    )
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Updated all agents successfully.")
