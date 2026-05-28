def estimate_cost(services, architecture=None):
    """
    Realistic cost estimator based on service + instance type.
    Used as fallback if LLM doesn't return a cost.
    """

    # Realistic pricing per service tier
    pricing = {
        # Compute
        "EC2_MICRO":    8.50,   # t2.micro
        "EC2_SMALL":    17.00,  # t3.small
        "EC2_MEDIUM":   30.00,  # t3.medium
        "EC2_LARGE":    60.00,  # t3.large
        "EC2":          30.00,  # default t3.medium

        # Database
        "RDS_MICRO":    25.00,  # db.t3.micro
        "RDS_MEDIUM":   55.00,  # db.t3.medium
        "RDS_LARGE":    110.00, # db.t3.large
        "RDS":          55.00,  # default

        # Storage & CDN
        "S3":           3.00,
        "CLOUDFRONT":   12.00,

        # Networking
        "VPC":          5.00,
        "ALB":          22.00,
        "ELB":          22.00,
        "ROUTE53":      1.00,

        # Compute alternatives
        "ECS":          40.00,
        "LAMBDA":       2.00,
        "ELASTICACHE":  25.00,

        # Other
        "DYNAMODB":     10.00,
        "SNS":          1.00,
        "SQS":          1.00,
        "IAM":          0.00,
        "ACM":          0.00,
        "CLOUDWATCH":   5.00,
        "CLOUDTRAIL":   2.00,
    }

    total = 0.0
    breakdown = []

    for service in services:
        key = service.upper().replace("AMAZON ", "").replace("AWS ", "").strip()
        cost = pricing.get(key, 8.00)
        total += cost
        breakdown.append(f"{service}: ${cost:.2f}/month")

    breakdown.append("─────────────────────")
    breakdown.append(f"💰 Estimated Total: ${total:.2f}/month")
    breakdown.append("⚠️ Actual costs vary by usage & region")

    return "\n".join(breakdown)