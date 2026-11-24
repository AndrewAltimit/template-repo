mock_provider "aws" {}

variables {
  availability_zones = ["us-east-1a", "us-east-1b"]
}

run "subnets_per_zone_and_no_ingress" {
  command = apply

  assert {
    condition     = length(aws_subnet.public) == 2
    error_message = "one public subnet per listed zone"
  }

  assert {
    condition     = aws_subnet.public["us-east-1b"].cidr_block == "10.42.1.0/24"
    error_message = "subnets are /24 slices in zone order"
  }

  assert {
    condition     = length(aws_security_group.node.ingress) == 0
    error_message = "the node security group must not allow inbound traffic"
  }

  assert {
    condition     = aws_vpc_endpoint.s3.vpc_endpoint_type == "Gateway"
    error_message = "the free S3 gateway endpoint keeps checkpoint traffic inside AWS"
  }
}

run "rejects_small_vpc" {
  command = plan

  variables {
    vpc_cidr = "10.0.0.0/24"
  }

  expect_failures = [var.vpc_cidr]
}
