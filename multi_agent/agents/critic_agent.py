from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from agents.state import AgentState
from agents.registry import register_agent
from agents.json_utils import invoke_with_json_retry, enforce_output_schema
load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    max_tokens=800,
    temperature=0.4
)

MAX_ITERATIONS = 1  # How many critic→code→review loops to allow


@register_agent("critic", "Critiques code and review output. Triggers improvement loops if needed.")
def critic_agent(state: AgentState) -> dict:
    context_dict = state.get("context_dict", {})
    code = context_dict.get("code", "No code available.")
    review = context_dict.get("review", "No review available.")
    plan = state.get("plan", [])
    iterations = state.get("iterations", 0)

    prompt = f"""
You are the Critic Agent in a multi-agent AI pipeline.

Code Output:
{code}

Review Notes:
{review}

Provide exactly 3 concrete, actionable improvement steps.
Each issue MUST follow this exact structure:
1. Issue: (specific line/logic)
2. Why it is wrong: (reasoning)
3. Exact fix: (code or instruction)

{enforce_output_schema()}
Put your 3 improvement steps in output_data as a JSON array of objects.
Example:
[
  {{"issue": "...", "why": "...", "fix": "..."}},
  {{"issue": "...", "why": "...", "fix": "..."}},
  {{"issue": "...", "why": "...", "fix": "..."}}
]
"""

    parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
    output_data = parsed.get("output_data", [])
    if isinstance(output_data, str):
        # fallback just in case it returns a string
        output_data = [{"issue": "string feedback", "why": "see fix", "fix": output_data}]
    context_dict["critic_feedback"] = {"issues": output_data}

    results = state.get("results", [])
    results.append("[critic] completed")

    # Trigger improvement loop if under iteration limit
    new_plan = plan
    new_iterations = iterations
    if iterations < MAX_ITERATIONS:
        new_plan = ["code", "review"] + plan
        new_iterations = iterations + 1
        results.append(f"[critic] Triggering improvement loop (iteration {new_iterations}/{MAX_ITERATIONS})")
        print(f"[Critic] Injecting code→review loop. Iteration {new_iterations}/{MAX_ITERATIONS}")

    return {
        "results": results,
        "context_dict": context_dict,
        "plan": new_plan,
        "iterations": new_iterations
    }
