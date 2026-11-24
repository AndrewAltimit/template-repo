# Network for measurement nodes: a small VPC with public subnets in several
# availability zones (GPU capacity differs by zone), no inbound access at all,
# and a free S3 gateway endpoint so checkpoint and weight traffic stays inside AWS.
#
# Nodes are reached, if ever, through SSM Session Manager, never SSH: the
# security group has no ingress rules.

data "aws_availability_zones" "available" {
  count = length(var.availability_zones) == 0 ? 1 : 0
  state = "available"
}

locals {
  azs = length(var.availability_zones) > 0 ? var.availability_zones : slice(
    data.aws_availability_zones.available[0].names, 0, min(var.az_count, length(data.aws_availability_zones.available[0].names))
  )
  name = "${var.project}-${var.environment}"
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = local.name }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = local.name }
}

resource "aws_subnet" "public" {
  for_each                = { for i, az in local.azs : az => i }
  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.name}-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.name}-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]
  tags              = { Name = "${local.name}-s3" }
}

resource "aws_security_group" "node" {
  name        = "${local.name}-node"
  description = "Measurement nodes: no inbound access; outbound for model downloads and AWS APIs"
  vpc_id      = aws_vpc.this.id
  tags        = { Name = "${local.name}-node" }
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.node.id
  description       = "Outbound HTTPS and DNS for package, model and AWS API access"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
