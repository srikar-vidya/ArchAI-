def generate_terraform(data):

    services = data["architecture"]["services"]

    tf_code = ""

    # EC2
    if "EC2" in services:

        tf_code += """
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"

  tags = {
    Name = "AI-Web-Server"
  }
}

"""

    # RDS
    if "RDS" in services:

        tf_code += """
resource "aws_db_instance" "db" {
  allocated_storage    = 20
  engine               = "mysql"
  instance_class       = "db.t3.micro"
  username             = "admin"
  password             = "password123"
  skip_final_snapshot  = true
}

"""

    # S3
    if "S3" in services:

        tf_code += """
resource "aws_s3_bucket" "storage" {
  bucket = "ai-cloud-storage-demo"
}

"""

    return tf_code