import os
import glob
import re

agent_files = glob.glob(r"c:\Users\dream\Desktop\multi_agent\multi_agent\agents\*_agent.py")
for file in agent_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace to model llama3-8b-8192 which has a 30k TPM limit on Groq and allow max_tokens=1024
    content = re.sub(
        r'llm = ChatGroq\(model="[^"]+", api_key=os\.getenv\("GROQ_API_KEY"\)[^\)]*\)',
        'llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"), max_tokens=2048)',
        content
    )
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Updated all agents to 30k TPM model successfully.")
