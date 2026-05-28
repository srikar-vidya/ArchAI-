def generate_terraform(data):
    services = data["architecture"]["services"]
    files = {}

    # provider.tf — always included
    files["provider.tf"] = """terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}"""

    # ec2.tf
    if "EC2" in services:
        files["ec2.tf"] = """resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  tags = {
    Name = "AI-Web-Server"
  }
}"""

    # rds.tf
    if "RDS" in services:
        files["rds.tf"] = """resource "aws_db_instance" "db" {
  allocated_storage   = 20
  engine              = "mysql"
  instance_class      = "db.t3.micro"
  username            = "admin"
  password            = "password123"
  skip_final_snapshot = true
}"""

    # s3.tf
    if "S3" in services:
        files["s3.tf"] = """resource "aws_s3_bucket" "storage" {
  bucket = "ai-cloud-storage-demo"
}"""

    # vpc.tf
    if "VPC" in services:
        files["vpc.tf"] = """resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "AI-VPC"
  }
}"""

    # alb.tf
    if "ALB" in services or "Application Load Balancer" in services:
        files["alb.tf"] = """resource "aws_lb" "main" {
  name               = "ai-cloud-alb"
  internal           = false
  load_balancer_type = "application"
}"""

    # cloudfront.tf
    if "CloudFront" in services:
        files["cloudfront.tf"] = """resource "aws_cloudfront_distribution" "cdn" {
  enabled = true
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "ai-origin"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  origin {
    domain_name = "example.com"
    origin_id   = "ai-origin"
  }
}"""

    # ecs.tf
    if "ECS" in services:
        files["ecs.tf"] = """resource "aws_ecs_cluster" "main" {
  name = "ai-ecs-cluster"
}"""

    return files