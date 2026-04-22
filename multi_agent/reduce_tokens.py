import os
import glob
import re

agent_files = glob.glob(r"c:\Users\dream\Desktop\multi_agent\multi_agent\agents\*.py")
for file in agent_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace anything >= 1500 back to 800
    new_content = re.sub(r'max_tokens\s*=\s*(1500|1800|1000)', 'max_tokens=800', content)
    new_content = re.sub(r'max_retries\s*=\s*4', 'max_retries=2', new_content) # Drop retries to beat timeout
    
    if new_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file}")
