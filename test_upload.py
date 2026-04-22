import requests
import json

csv_content = b"name,age,score\nAlice,25,88.5\nBob,30,72.0\nCarol,22,95.3\nDave,28,61.8\n"

files = {"file": ("test.csv", csv_content, "text/csv")}

try:
    r = requests.post("http://127.0.0.1:5000/analyze-file", files=files, timeout=90)
    data = r.json()
    print("HTTP Status:", r.status_code)
    print("Summary (first 300):", data.get("summary", "")[:300])
    print("Chart present:", bool(data.get("chart_b64")))
    print("Insights:", str(data.get("insights", ""))[:300])
    print("Error:", data.get("error"))
except Exception as e:
    print("FAILED:", e)
