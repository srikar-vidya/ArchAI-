from app.llm_engine import generate_architecture
from app.terraform_generator import generate_terraform

result = generate_architecture(
    "Build a scalable ecommerce application with database and load balancer"
)

terraform_code = generate_terraform(result)

with open("outputs/main.tf", "w") as file:
    file.write(terraform_code)

print("Terraform file generated successfully.")