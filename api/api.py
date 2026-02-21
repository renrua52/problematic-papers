import os, json
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_API_BASE"]
)

def chat(prompt, model="gemini-2.5-flash-lite"):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content

import re

def extract_score(s):
    m = re.search(r"<SCORE>\s*([+-]?\d+(?:\.\d+)?)\s*</SCORE>", s)
    if m:
        val_str = m.group(1)
        val = float(val_str) if ("." in val_str) else int(val_str)
    return val

