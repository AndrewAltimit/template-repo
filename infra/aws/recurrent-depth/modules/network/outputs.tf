output "vpc_id" {
  value = aws_vpc.this.id
}

output "subnet_ids" {
  description = "Public subnet ids, one per zone, keyed by zone."
  value       = { for az, s in aws_subnet.public : az => s.id }
}

output "security_group_id" {
  description = "Node security group (no ingress)."
  value       = aws_security_group.node.id
}
