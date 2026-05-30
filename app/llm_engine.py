from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import re
from app.prompts import SYSTEM_PROMPT

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def _clean_json(raw: str) -> str:
    """Strip markdown fences and any leading/trailing non-JSON text."""
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    # Find the first { and last } to extract pure JSON
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start != -1 and end != 0:
        cleaned = cleaned[start:end]
    return cleaned


def generate_architecture(user_input: str) -> dict:
    """Call the LLM and return a validated architecture dict."""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_input},
            ],
            temperature=0.3,   # lower = more deterministic / consistent JSON
        )
        raw = response.choices[0].message.content
        cleaned = _clean_json(raw)
        data = json.loads(cleaned)

        # ── Normalise: ensure all expected fields exist ───────────────────────
        arch = data.setdefault("architecture", {})
        arch.setdefault("services",        ["EC2", "RDS", "S3", "VPC", "ALB"])
        arch.setdefault("instance_type",   "t3.medium")
        arch.setdefault("instance_count",  1)
        arch.setdefault("db_instance_class", "db.t3.medium")
        arch.setdefault("db_engine",       "mysql")
        arch.setdefault("storage_gb",      100)
        arch.setdefault("multi_az",        False)
        arch.setdefault("enable_https",    True)

        return data

    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw output: {raw}")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")