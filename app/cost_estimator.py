"""
Cost Estimator — prices match exactly what terraform_generator.py deploys.
All costs are approximate USD/month (us-east-1, on-demand, 730 hrs).
"""

EC2_PRICING = {
    "t2.micro":     8.50,
    "t2.small":    17.00,
    "t2.medium":   33.00,
    "t3.micro":     8.50,
    "t3.small":    17.00,
    "t3.medium":   30.00,
    "t3.large":    60.00,
    "t3.xlarge":  120.00,
    "t3.2xlarge": 240.00,
    "c5.large":    78.00,
    "c5.xlarge":  156.00,
    "c5.2xlarge": 312.00,
    "m5.large":    70.00,
    "m5.xlarge":  140.00,
    "m5.2xlarge": 280.00,
}

RDS_PRICING = {
    "db.t3.micro":     25.00,
    "db.t3.small":     38.00,
    "db.t3.medium":    55.00,
    "db.t3.large":    110.00,
    "db.r5.large":    185.00,
    "db.r5.xlarge":   370.00,
    "db.r5.2xlarge":  480.00,
}

SERVICE_PRICING = {
    "S3":                  3.00,
    "CLOUDFRONT":         12.00,
    "VPC":                 5.00,
    "ALB":                22.00,
    "ELB":                22.00,
    "ROUTE53":             1.00,
    "ECS":                40.00,
    "EKS":                73.00,
    "LAMBDA":              2.00,
    "ELASTICACHE":        25.00,
    "DYNAMODB":           10.00,
    "SNS":                 1.00,
    "SQS":                 1.00,
    "IAM":                 0.00,
    "ACM":                 0.00,
    "CLOUDWATCH":          5.00,
    "CLOUDTRAIL":          2.00,
    "ELASTICBEANSTALK":    0.00,
    "ELASTIC BEANSTALK":   0.00,
    "API GATEWAY":        10.00,
    "APIGATEWAY":         10.00,
    "SECRETS MANAGER":     1.00,
    "SECRETSMANAGER":      1.00,
    "WAF":                 5.00,
    "COGNITO":             3.00,
}


def _normalize_service_key(service: str) -> str:
    return service.upper().replace("AMAZON ", "").replace("AWS ", "").strip()


def estimate_cost(services: list, architecture: dict = None) -> str:
    """
    Build an itemized cost breakdown that exactly mirrors what
    terraform_generator.py will provision.
    """
    # ── Extract architecture details ──────────────────────────────────────────
    instance_type  = "t3.medium"
    instance_count = 1
    db_instance    = "db.t3.medium"
    db_engine_label = "MySQL"
    storage_gb     = 100
    multi_az       = False

    if architecture:
        arch = architecture.get("architecture", {})

        # EC2
        instance_type  = arch.get("instance_type", "t3.medium").lower()
        instance_count = int(arch.get("instance_count", 1))

        # RDS — prefer explicit field, fall back to parsing "database" string
        if arch.get("db_instance_class"):
            db_instance = arch["db_instance_class"].lower()
        else:
            db_raw = arch.get("database", "").lower()
            for size in ["db.r5.2xlarge", "db.r5.xlarge", "db.r5.large",
                         "db.t3.large", "db.t3.medium", "db.t3.small", "db.t3.micro"]:
                if size in db_raw:
                    db_instance = size
                    break

        # Engine label
        db_engine = arch.get("db_engine", "").lower()
        db_raw    = arch.get("database", "").lower()
        if "aurora-postgresql" in db_engine or "aurora postgresql" in db_raw:
            db_engine_label = "Aurora PostgreSQL"
        elif "aurora" in db_engine or "aurora" in db_raw:
            db_engine_label = "Aurora MySQL"
        elif "postgres" in db_engine or "postgres" in db_raw:
            db_engine_label = "PostgreSQL"
        else:
            db_engine_label = "MySQL"

        storage_gb = int(arch.get("storage_gb", 100))
        multi_az   = bool(arch.get("multi_az", False))

    # ── Build breakdown ───────────────────────────────────────────────────────
    total     = 0.0
    breakdown = []

    for service in services:
        key = _normalize_service_key(service)

        if key == "EC2":
            unit_cost = EC2_PRICING.get(instance_type, 30.00)
            cost      = unit_cost * instance_count
            label     = (f"EC2 {instance_type} × {instance_count} (24/7)"
                         if instance_count > 1
                         else f"EC2 {instance_type} (24/7)")
            breakdown.append(f"{label}: {cost:.2f} USD/month")

        elif key == "RDS":
            cost = RDS_PRICING.get(db_instance, 55.00)
            if multi_az:
                cost *= 2  # Multi-AZ doubles the RDS cost
            label = f"RDS {db_instance} {db_engine_label}"
            if multi_az:
                label += " (Multi-AZ)"
            breakdown.append(f"{label}: {cost:.2f} USD/month")

        elif key == "S3":
            # Estimate based on storage_gb
            cost = max(3.00, round(storage_gb * 0.023, 2))
            breakdown.append(f"S3 {storage_gb}GB: {cost:.2f} USD/month")

        else:
            cost = SERVICE_PRICING.get(key, 8.00)
            breakdown.append(f"{service}: {cost:.2f} USD/month")

        total += cost

    breakdown.append("─" * 45)
    breakdown.append(f"💰 Estimated Total: {total:.0f} USD/month")
    breakdown.append("⚠️  Actual costs vary by usage & region")

    return "\n".join(breakdown)