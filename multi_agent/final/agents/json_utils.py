import json
import re


def clean_json_string(raw_text: str) -> str:
    cleaned = re.sub(r'```(?:json)?', '', raw_text)
    cleaned = cleaned.replace('```', '')
    cleaned = cleaned.strip()
    cleaned = re.sub(r',\s*\}', '}', cleaned)
    cleaned = re.sub(r',\s*\]', ']', cleaned)
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"')
    cleaned = cleaned.replace('\u2018', "'").replace('\u2019', "'")
    return cleaned


def extract_outermost_json(raw_text: str) -> str:
    """
    Walk character-by-character to find the outermost { } block.
    Handles nesting, strings, and escaped characters correctly.
    Far more reliable than a simple regex on LLM output.
    """
    start = raw_text.find('{')
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(raw_text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return raw_text[start:i + 1]
    return raw_text[start:]


def repair_json(json_str: str) -> str:
    """
    Heuristic line-by-line repair for common LLM JSON mistakes.
    """
    lines = json_str.splitlines()
    repaired = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Drop lines that look like stray prose (no JSON punctuation)
        if (stripped and
                not stripped.startswith('"') and
                not stripped.startswith('{') and
                not stripped.startswith('}') and
                not stripped.startswith('[') and
                not stripped.startswith(']') and
                ':' not in stripped and
                not stripped.startswith(',')):
            continue
        repaired.append(line)
    return '\n'.join(repaired)


def parse_agent_json(raw_text: str, fallback_key: str = "output_data") -> dict:
    """
    Attempts to extract and parse JSON from raw LLM output.
    Never raises — always returns a dict with status=success so the pipeline continues.
    """
    if not raw_text or not raw_text.strip():
        return {"thought_process": "Empty response.", "status": "success", fallback_key: ""}

    json_str = extract_outermost_json(raw_text)

    if not json_str:
        return {
            "thought_process": "No JSON block found.",
            "status": "success",
            fallback_key: raw_text.strip()
        }

    json_str = clean_json_string(json_str)

    # Attempt 1: direct parse
    try:
        data = json.loads(json_str)
        data["status"] = "success"
        return data
    except json.JSONDecodeError as e:
        print(f"[JSON] Direct parse failed: {e}. Trying repair...")

    # Attempt 2: repaired parse
    try:
        data = json.loads(repair_json(json_str))
        data["status"] = "success"
        return data
    except json.JSONDecodeError:
        print(f"[JSON] Repair parse failed. Falling back to raw text.")

    # Attempt 3: just return the raw string — never crash the pipeline
    return {
        "thought_process": "JSON parsing failed after all repair attempts.",
        "status": "success",
        fallback_key: raw_text.strip()
    }


def enforce_output_schema() -> str:
    return """
CRITICAL: Your ENTIRE response must be a single valid JSON object.
No markdown. No code fences. No text before or after the JSON.
Start with { and end with }.
Use EXACTLY this schema:
{
  "thought_process": "your brief reasoning here",
  "status": "success",
  "output_data": "your result here"
}
output_data must be a plain string or a JSON array. Never leave it null.
"""


def invoke_with_json_retry(llm, prompt: str, max_retries: int = 4, fallback_key: str = "output_data") -> dict:
    """
    Calls the LLM with automatic retry on JSON parse failure.
    After all retries, returns a safe fallback instead of raising — pipeline never crashes.
    """
    last_err = ""
    last_raw = ""

    for attempt in range(max_retries):
        p = prompt
        if attempt > 0:
            p += f"""

[SYSTEM - RETRY ATTEMPT {attempt}/{max_retries - 1}]
Your previous response could not be parsed as JSON.
Error: {last_err}
What you returned (first 400 chars): {last_raw[:400]}

FIX: Respond with ONLY a raw JSON object.
- Start with {{
- End with }}
- No markdown, no backticks, no explanation outside the JSON
- output_data must not be null or empty
"""
        try:
            response = llm.invoke(p)
            last_raw = response.content or ""
            parsed = parse_agent_json(last_raw, fallback_key=fallback_key)
            if parsed.get("status") == "success":
                out = parsed.get(fallback_key, "")
                if out or out == []:  # accept empty list but not None
                    return parsed
                last_err = "output_data was empty or None."
            else:
                last_err = "Status was not success."
        except Exception as e:
            last_err = str(e)
            print(f"[RETRY {attempt}] Exception during LLM call: {e}")

    # Safe fallback — pipeline always continues
    print(f"[JSON UTILS] All {max_retries} retries exhausted. Returning safe fallback.")
    return {
        "thought_process": "Max retries exhausted.",
        "status": "success",
        fallback_key: last_raw.strip() if last_raw else "Agent produced no output after retries."
    }
