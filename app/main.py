from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.llm_engine import generate_architecture
from app.terraform_generator import generate_terraform
from app.cost_estimator import estimate_cost

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/")
def home():
    return {"message": "CloudForge API Running"}

@app.post("/generate")
def generate(request: PromptRequest):

    architecture = generate_architecture(request.prompt)

    services = architecture["architecture"]["services"]

    # Try LLM cost first (most accurate), fallback to estimator
    llm_cost = (
        architecture.get("architecture", {}).get("estimated_cost")
        or architecture.get("estimated_cost")
    )

    # Use LLM cost breakdown if available
    cost_breakdown = architecture.get("cost_breakdown", {})

    if llm_cost:
        # Format LLM breakdown nicely
        if cost_breakdown:
            lines = [f"{k}: {v}" for k, v in cost_breakdown.items()]
            lines.append("─────────────────────")
            lines.append(f"💰 Estimated Total: {llm_cost}")
            lines.append("⚠️ Actual costs vary by usage & region")
            cost = "\n".join(lines)
        else:
            cost = f"💰 Estimated Total: {llm_cost}\n⚠️ Actual costs vary by usage & region"
    else:
        # Fallback to dynamic estimator
        cost = estimate_cost(services, architecture)

    terraform_files = generate_terraform(architecture)

    return {
        "architecture": architecture,
        "services": services,
        "estimated_cost": cost,
        "terraform_files": terraform_files
    }