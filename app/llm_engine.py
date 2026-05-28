from openai import OpenAI
from dotenv import load_dotenv
import os
import json
from app.prompts import SYSTEM_PROMPT

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def generate_architecture(user_input):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # free & powerful
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]
    )
    output = response.choices[0].message.content
    cleaned = output.replace("```json", "").replace("```", "")
    return json.loads(cleaned)