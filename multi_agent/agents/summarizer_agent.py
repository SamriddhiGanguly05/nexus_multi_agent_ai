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
    max_tokens=1200,
    temperature=0.2
)

def prepare_summary_context(context_dict):
    """
    Trim context heavily to ensure the summarizer stays concise.
    """
    critic = context_dict.get("critic_feedback", "")
    if isinstance(critic, dict):
        critic = str(critic.get("issues", ""))

    code = str(context_dict.get("code", ""))
    # If code is very long, truncate and note it
    if len(code) > 800:
        code = code[:800] + "\n... [code truncated for brevity]"

    return {
        "research": str(context_dict.get("research", ""))[:600],
        "code": code,
        "review": str(context_dict.get("review", ""))[:400],
        "critic": str(critic)[:400]
    }


@register_agent("summarizer", "Final agent — synthesizes all outputs into a complete, formatted response.", is_terminal=True)
def summarizer_agent(state: AgentState) -> dict:
    context_dict = state.get("context_dict", {})
    original_task = state.get("task", "")

    context_summary = prepare_summary_context(context_dict)

    prompt = f"""
You are the Master Synthesizer — the FINAL agent in a multi-agent AI pipeline.

Original Task: {original_task}

Agent Outputs (trimmed):
- Research: {context_summary['research']}
- Code: {context_summary['code']}
- Review: {context_summary['review']}
- Critic: {context_summary['critic']}

YOUR OUTPUT MUST FOLLOW THESE STRICT RULES:
1. Total word count: 150–250 words MAXIMUM. Be extremely concise.
2. Use CLEAN MARKDOWN ONLY — no nested JSON, no dicts, no objects.
3. Use bullet points (2–3 per section). NO paragraphs.
4. Do NOT repeat information across sections.
5. Each section header must appear EXACTLY as written below.

OUTPUT FORMAT (follow exactly):

## Executive Summary
- [1 crisp sentence about what was done]
- [1 sentence on method or key result]

## Key Approach
- [main technique or algorithm used]
- [important design decision]

## Final Code Insight
- [what the generated code does in 1 line]
- [1 notable implementation detail, if applicable]

## Key Patterns
- [key pattern or best practice identified]
- [one takeaway or future recommendation]

DO NOT write paragraphs. DO NOT add extra sections. DO NOT expand unnecessarily.
Aim for minimal, high-signal bullets only.

{enforce_output_schema()}
Put the complete structured Markdown report in output_data as a plain string.
"""

    required_sections = [
        "Executive Summary",
        "Key Approach",
        "Final Code Insight",
        "Key Patterns"
    ]

    results = state.get("results", [])
    max_attempts = 3
    final_output = ""

    for attempt in range(max_attempts):
        print(f"[Summarizer] Generating summary (Attempt {attempt + 1}/{max_attempts})...")
        parsed = invoke_with_json_retry(llm, prompt, max_retries=2)
        output = parsed.get("output_data", "")

        # If output_data is a dict (nested JSON), flatten it to markdown
        if isinstance(output, dict):
            output = _flatten_dict_to_markdown(output)

        output_str = str(output).strip()

        missing = [sec for sec in required_sections if sec.lower() not in output_str.lower()]

        if not missing and output_str:
            final_output = output_str
            if attempt > 0:
                results.append(f"[summarizer] ✅ Output completed after {attempt + 1} attempts")
            else:
                results.append("[summarizer] completed")
            break
        else:
            print(f"[Summarizer] Warning: Missing sections on attempt {attempt+1}: {missing}")
            results.append(f"[summarizer] ⚠️ Missing {missing} — retrying...")
            if output_str:
                final_output = output_str  # keep best so far

    if not final_output:
        final_output = "Summarizer produced no valid output."

    return {
        "final_output": final_output,
        "results": results
    }


def _flatten_dict_to_markdown(d: dict) -> str:
    """Convert a nested dict output_data into clean Markdown."""
    lines = []
    for section, content in d.items():
        lines.append(f"## {section}")
        if isinstance(content, list):
            for item in content:
                lines.append(f"- {item}")
        elif isinstance(content, dict):
            for k, v in content.items():
                lines.append(f"- **{k}**: {v}")
        else:
            lines.append(f"- {content}")
        lines.append("")
    return "\n".join(lines)
