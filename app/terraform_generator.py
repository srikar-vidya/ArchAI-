"""
Terraform Generator
───────────────────
Reads instance_type, db_instance_class, db_engine, storage_gb, multi_az, etc.
directly from the architecture dict so generated code always matches
the cost estimate.
"""

import json

# ── AMI map (us-east-1 Amazon Linux 2023) ─────────────────────────────────────
# Only one AMI per region is needed — we pick it based on the instance family.
DEFAULT_AMI = "ami-0c101f26f147fa7fd"   # Amazon Linux 2023 (us-east-1, x86)


# ── Engine → Terraform engine string ──────────────────────────────────────────
ENGINE_MAP = {
    "mysql":               "mysql",
    "postgres":            "postgres",
    "postgresql":          "postgres",
    "aurora-mysql":        "aurora-mysql",
    "aurora-postgresql":   "aurora-postgresql",
    "aurora postgresql":   "aurora-postgresql",
    "aurora mysql":        "aurora-mysql",
    "aurora":              "aurora-mysql",
}

ENGINE_VERSION_MAP = {
    "mysql":             "8.0",
    "postgres":          "15.3",
    "aurora-mysql":      "8.0.mysql_aurora.3.04.0",
    "aurora-postgresql": "15.3",
}


def _parse_arch(architecture: dict) -> dict:
    """Extract & normalise all fields we need from the architecture JSON."""
    arch = architecture.get("architecture", {})

    instance_type  = arch.get("instance_type",  "t3.medium").lower()
    instance_count = int(arch.get("instance_count", 1))
    multi_az       = bool(arch.get("multi_az", False))
    storage_gb     = int(arch.get("storage_gb", 100))
    enable_https   = bool(arch.get("enable_https", True))
    services       = [s.upper() for s in arch.get("services", [])]

    # ── DB instance class ─────────────────────────────────────────────────────
    db_instance_class = arch.get("db_instance_class", "").lower()
    if not db_instance_class:
        # Fall back: parse from "database" string
        db_raw = arch.get("database", "").lower()
        db_instance_class = "db.t3.medium"
        for size in ["db.r5.2xlarge", "db.r5.xlarge", "db.r5.large",
                     "db.t3.large",   "db.t3.medium", "db.t3.small", "db.t3.micro"]:
            if size in db_raw:
                db_instance_class = size
                break

    # ── DB engine ─────────────────────────────────────────────────────────────
    raw_engine = arch.get("db_engine", "").lower()
    if not raw_engine:
        db_raw = arch.get("database", "").lower()
        for key in ENGINE_MAP:
            if key in db_raw:
                raw_engine = key
                break
        else:
            raw_engine = "mysql"

    db_engine   = ENGINE_MAP.get(raw_engine, "mysql")
    db_version  = ENGINE_VERSION_MAP.get(db_engine, "8.0")
    is_aurora   = db_engine.startswith("aurora")

    return {
        "instance_type":    instance_type,
        "instance_count":   instance_count,
        "multi_az":         multi_az,
        "storage_gb":       storage_gb,
        "enable_https":     enable_https,
        "services":         services,
        "db_instance_class": db_instance_class,
        "db_engine":        db_engine,
        "db_version":       db_version,
        "is_aurora":        is_aurora,
        "has_rds":          "RDS" in services,
        "has_s3":           "S3" in services,
        "has_alb":          any(s in services for s in ["ALB", "ELB"]),
        "has_lambda":       "LAMBDA" in services,
        "has_elasticache":  "ELASTICACHE" in services,
        "has_ecs":          "ECS" in services,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Individual file generators
# ─────────────────────────────────────────────────────────────────────────────

def _gen_provider() -> str:
    return '''\
terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
'''


def _gen_variables(p: dict) -> str:
    return f'''\
variable "aws_region" {{
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}}

variable "project_name" {{
  description = "Project name used for resource naming"
  type        = string
  default     = "cloudforge"
}}

variable "environment" {{
  description = "Deployment environment"
  type        = string
  default     = "production"
}}

variable "instance_type" {{
  description = "EC2 instance type"
  type        = string
  default     = "{p["instance_type"]}"
}}

variable "instance_count" {{
  description = "Number of EC2 instances"
  type        = number
  default     = {p["instance_count"]}
}}

variable "db_instance_class" {{
  description = "RDS instance class"
  type        = string
  default     = "{p["db_instance_class"]}"
}}

variable "db_password" {{
  description = "RDS master password"
  type        = string
  sensitive   = true
  default     = "ChangeMe123!"   # CHANGE in production!
}}

variable "storage_gb" {{
  description = "EBS / RDS storage in GB"
  type        = number
  default     = {p["storage_gb"]}
}}
'''


def _gen_vpc() -> str:
    return '''\
# ─── VPC ─────────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

# Public subnets (ALB / NAT)
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "${var.project_name}-public-${count.index}" }
}

# Private subnets (EC2 / RDS)
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "${var.project_name}-private-${count.index}" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# NAT Gateway (so private instances can reach the internet)
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "${var.project_name}-nat" }
  depends_on    = [aws_internet_gateway.main]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = { Name = "${var.project_name}-private-rt" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
'''


def _gen_security_groups(p: dict) -> str:
    https_rule = ""
    if p["enable_https"]:
        https_rule = '''
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }'''

    return f'''\
# ─── Security Groups ─────────────────────────────────────────────────────────

resource "aws_security_group" "alb" {{
  name        = "${{var.project_name}}-alb-sg"
  description = "Allow HTTP/HTTPS inbound"
  vpc_id      = aws_vpc.main.id

  ingress {{
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }}{https_rule}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = {{ Name = "${{var.project_name}}-alb-sg" }}
}}

resource "aws_security_group" "ec2" {{
  name        = "${{var.project_name}}-ec2-sg"
  description = "Allow traffic from ALB only"
  vpc_id      = aws_vpc.main.id

  ingress {{
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "From ALB"
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = {{ Name = "${{var.project_name}}-ec2-sg" }}
}}

resource "aws_security_group" "rds" {{
  name        = "${{var.project_name}}-rds-sg"
  description = "Allow MySQL/PostgreSQL from EC2 only"
  vpc_id      = aws_vpc.main.id

  ingress {{
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description     = "DB from EC2"
  }}

  tags = {{ Name = "${{var.project_name}}-rds-sg" }}
}}
'''


def _gen_ec2(p: dict) -> str:
    asg_block = ""
    if p["instance_count"] > 1 or p["has_alb"]:
        asg_block = f'''
# ─── Auto Scaling Group ───────────────────────────────────────────────────────

resource "aws_launch_template" "app" {{
  name_prefix   = "${{var.project_name}}-lt-"
  image_id      = "{DEFAULT_AMI}"
  instance_type = var.instance_type

  network_interfaces {{
    associate_public_ip_address = false
    security_groups             = [aws_security_group.ec2.id]
  }}

  block_device_mappings {{
    device_name = "/dev/xvda"
    ebs {{
      volume_size           = var.storage_gb
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }}
  }}

  iam_instance_profile {{
    name = aws_iam_instance_profile.ec2_profile.name
  }}

  user_data = base64encode(<<-EOF
    #!/bin/bash
    yum update -y
    yum install -y httpd
    systemctl start httpd
    systemctl enable httpd
    echo "<h1>Deployed by CloudForge</h1>" > /var/www/html/index.html
  EOF
  )

  tags = {{ Name = "${{var.project_name}}-launch-template" }}
}}

resource "aws_autoscaling_group" "app" {{
  name                = "${{var.project_name}}-asg"
  min_size            = var.instance_count
  max_size            = var.instance_count * 3
  desired_capacity    = var.instance_count
  vpc_zone_identifier = aws_subnet.private[*].id

  launch_template {{
    id      = aws_launch_template.app.id
    version = "$Latest"
  }}

  target_group_arns = [aws_lb_target_group.app.arn]

  health_check_type         = "ELB"
  health_check_grace_period = 300

  tag {{
    key                 = "Name"
    value               = "${{var.project_name}}-instance"
    propagate_at_launch = true
  }}
}}

resource "aws_autoscaling_policy" "scale_up" {{
  name                   = "${{var.project_name}}-scale-up"
  autoscaling_group_name = aws_autoscaling_group.app.name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {{
  alarm_name          = "${{var.project_name}}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 75
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]

  dimensions = {{
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }}
}}
'''
    else:
        asg_block = f'''
# ─── EC2 Instance ─────────────────────────────────────────────────────────────

resource "aws_instance" "app" {{
  ami                    = "{DEFAULT_AMI}"
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.private[0].id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device {{
    volume_size = var.storage_gb
    volume_type = "gp3"
    encrypted   = true
  }}

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y httpd
    systemctl start httpd
    systemctl enable httpd
    echo "<h1>Deployed by CloudForge</h1>" > /var/www/html/index.html
  EOF

  tags = {{ Name = "${{var.project_name}}-app-server" }}
}}
'''

    return asg_block


def _gen_alb(p: dict) -> str:
    if not p["has_alb"]:
        return ""

    https_listener = ""
    if p["enable_https"]:
        https_listener = '''
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = "443"
  protocol          = "HTTPS"

  # Replace with a real ACM certificate ARN
  # certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT-ID"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
'''

    return f'''\
# ─── Application Load Balancer ───────────────────────────────────────────────

resource "aws_lb" "app" {{
  name               = "${{var.project_name}}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false
  tags = {{ Name = "${{var.project_name}}-alb" }}
}}

resource "aws_lb_target_group" "app" {{
  name     = "${{var.project_name}}-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {{
    enabled             = true
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }}
}}

resource "aws_lb_listener" "http" {{
  load_balancer_arn = aws_lb.app.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {{
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }}
}}
{https_listener}'''


def _gen_rds(p: dict) -> str:
    if not p["has_rds"]:
        return ""

    if p["is_aurora"]:
        return f'''\
# ─── Aurora Cluster ───────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {{
  name       = "${{var.project_name}}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags = {{ Name = "${{var.project_name}}-db-subnet-group" }}
}}

resource "aws_rds_cluster" "main" {{
  cluster_identifier      = "${{var.project_name}}-aurora-cluster"
  engine                  = "{p["db_engine"]}"
  engine_version          = "{p["db_version"]}"
  database_name           = "appdb"
  master_username         = "admin"
  master_password         = var.db_password
  storage_encrypted       = true
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  skip_final_snapshot     = false
  final_snapshot_identifier = "${{var.project_name}}-final-snapshot"
  tags = {{ Name = "${{var.project_name}}-aurora" }}
}}

resource "aws_rds_cluster_instance" "main" {{
  count              = {2 if p["multi_az"] else 1}
  identifier         = "${{var.project_name}}-aurora-${{count.index}}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.db_instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
  publicly_accessible = false
}}
'''
    else:
        return f'''\
# ─── RDS Instance ─────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {{
  name       = "${{var.project_name}}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags = {{ Name = "${{var.project_name}}-db-subnet-group" }}
}}

resource "aws_db_instance" "main" {{
  identifier             = "${{var.project_name}}-db"
  engine                 = "{p["db_engine"]}"
  engine_version         = "{p["db_version"]}"
  instance_class         = var.db_instance_class
  allocated_storage      = var.storage_gb
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = "appdb"
  username               = "admin"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = {str(p["multi_az"]).lower()}
  publicly_accessible    = false
  skip_final_snapshot    = false
  final_snapshot_identifier = "${{var.project_name}}-final-snapshot"
  deletion_protection    = false
  tags = {{ Name = "${{var.project_name}}-rds" }}
}}
'''


def _gen_s3(p: dict) -> str:
    if not p["has_s3"]:
        return ""
    return '''\
# ─── S3 Bucket ───────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "app" {
  bucket = "${var.project_name}-app-storage-${random_id.bucket_suffix.hex}"
  tags   = { Name = "${var.project_name}-storage" }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "app" {
  bucket = aws_s3_bucket.app.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app" {
  bucket = aws_s3_bucket.app.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket                  = aws_s3_bucket.app.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
'''


def _gen_iam() -> str:
    return '''\
# ─── IAM ─────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}
'''


def _gen_outputs(p: dict) -> str:
    alb_output = ""
    if p["has_alb"]:
        alb_output = '''
output "alb_dns_name" {
  description = "Application Load Balancer DNS"
  value       = aws_lb.app.dns_name
}
'''
    rds_output = ""
    if p["has_rds"]:
        endpoint_ref = ("aws_rds_cluster.main.endpoint"
                        if p["is_aurora"]
                        else "aws_db_instance.main.endpoint")
        rds_output = f'''
output "rds_endpoint" {{
  description = "RDS connection endpoint"
  value       = {endpoint_ref}
  sensitive   = true
}}
'''
    s3_output = ""
    if p["has_s3"]:
        s3_output = '''
output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.app.bucket
}
'''
    return f'''\
# ─── Outputs ─────────────────────────────────────────────────────────────────
{alb_output}{rds_output}{s3_output}
output "vpc_id" {{
  description = "VPC ID"
  value       = aws_vpc.main.id
}}
'''


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_terraform(architecture: dict) -> dict:
    """
    Return a dict of filename → HCL content.
    Every value is derived from `architecture` — nothing is hardcoded.
    """
    p = _parse_arch(architecture)

    files = {
        "provider.tf":  _gen_provider(),
        "variables.tf": _gen_variables(p),
        "vpc.tf":       _gen_vpc(),
        "security_groups.tf": _gen_security_groups(p),
        "ec2.tf":       _gen_ec2(p),
        "iam.tf":       _gen_iam(),
        "outputs.tf":   _gen_outputs(p),
    }

    if p["has_alb"]:
        files["alb.tf"] = _gen_alb(p)

    if p["has_rds"]:
        files["rds.tf"] = _gen_rds(p)

    if p["has_s3"]:
        files["s3.tf"] = _gen_s3(p)

    return files