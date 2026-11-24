# Launch templates for measurement nodes, one per tier. Nothing here starts
# an instance: scripts/node.sh launches one from a template for a single run,
# and the node terminates itself when the run ends or its deadline passes.
#
# Safety settings every template carries:
#   - instance-initiated shutdown terminates (power-off ends billing)
#   - the bootstrap arms a shutdown timer before doing anything else
#   - IMDSv2 only; instance tags exposed to the node for RunId and MaxHours
#   - no key pair, no inbound security group rules

data "aws_ssm_parameter" "ami" {
  count = var.ami_id == null ? 1 : 0
  name  = var.ami_ssm_parameter
}

locals {
  ami_id = var.ami_id != null ? var.ami_id : data.aws_ssm_parameter.ami[0].value

  bootstrap = {
    for tier, t in var.tiers : tier => templatefile("${path.module}/bootstrap.sh.tftpl", {
      bucket         = var.bucket_name
      region         = var.aws_region
      tier           = tier
      hard_cap_hours = t.max_hours
    })
  }
}

resource "aws_launch_template" "node" {
  for_each = var.tiers

  name                                 = "${var.project}-${var.environment}-${each.key}"
  description                          = "recurrent-depth ${each.key} node: ${each.value.instance_type}, at most ${each.value.max_hours} h"
  image_id                             = local.ami_id
  instance_type                        = each.value.instance_type
  instance_initiated_shutdown_behavior = "terminate"
  ebs_optimized                        = true
  update_default_version               = true
  user_data                            = base64encode(local.bootstrap[each.key])

  iam_instance_profile {
    name = var.instance_profile_name
  }

  # Security group at the top level rather than in network_interfaces, so a
  # launch can pick the subnet (zone with capacity) with --subnet-id. Public
  # addresses come from the subnet's map_public_ip_on_launch.
  vpc_security_group_ids = [var.security_group_id]

  block_device_mappings {
    device_name = var.root_device_name
    ebs {
      volume_size           = each.value.root_volume_gb
      volume_type           = "gp3"
      iops                  = 6000
      throughput            = 1000 # MB/s; the gp3 default of 125 makes a 750 GB load take ~100 min
      encrypted             = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  dynamic "instance_market_options" {
    for_each = each.value.spot ? [1] : []
    content {
      market_type = "spot"
      spot_options {
        instance_interruption_behavior = "terminate"
        spot_instance_type             = "one-time"
      }
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Project      = var.project
      Environment  = var.environment
      Tier         = each.key
      HardCapHours = tostring(each.value.max_hours)
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags = {
      Project = var.project
      Tier    = each.key
    }
  }
}
