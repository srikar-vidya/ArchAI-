from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.llm_engine import generate_architecture
from app.terraform_generator import generate_terraform
from app.cost_estimator import estimate_cost

app = FastAPI(title="CloudForge API", version="2.0")

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
    return {"message": "CloudForge API Running", "version": "2.0"}


@app.post("/generate")
def generate(request: PromptRequest):
    try:
        # 1️⃣  Generate architecture from LLM
        architecture = generate_architecture(request.prompt)
        arch         = architecture["architecture"]
        services     = arch.get("services", [])

        # 2️⃣  Cost estimate — uses same instance_type / db_instance_class the
        #      terraform generator will use (both read from `architecture`)
        cost = estimate_cost(services, architecture)

        # 3️⃣  Terraform files — all values come from `architecture`, never hardcoded
        terraform_files = generate_terraform(architecture)

        return {
            "architecture":    architecture,
            "services":        services,
            "estimated_cost":  cost,
            "terraform_files": terraform_files,
            # Expose key sizing info so the frontend can display it clearly
            "summary": {
                "instance_type":     arch.get("instance_type"),
                "instance_count":    arch.get("instance_count", 1),
                "db_instance_class": arch.get("db_instance_class"),
                "db_engine":         arch.get("db_engine"),
                "storage_gb":        arch.get("storage_gb"),
                "multi_az":          arch.get("multi_az", False),
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")