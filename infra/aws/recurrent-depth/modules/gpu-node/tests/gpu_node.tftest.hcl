mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }
}

variables {
  bucket_name           = "recurrent-depth-results-dev-test"
  instance_profile_name = "recurrent-depth-dev-node"
  security_group_id     = "sg-0123456789abcdef0"
}

run "templates_are_self_terminating" {
  command = apply

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : lt.instance_initiated_shutdown_behavior == "terminate"])
    error_message = "power-off must terminate the instance so billing stops"
  }

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : lt.metadata_options[0].http_tokens == "required"])
    error_message = "IMDSv2 only"
  }

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : lt.metadata_options[0].instance_metadata_tags == "enabled"])
    error_message = "the bootstrap reads RunId and MaxHours from instance tags"
  }

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : lt.key_name == null || lt.key_name == ""])
    error_message = "no SSH key pairs"
  }

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : lt.block_device_mappings[0].ebs[0].encrypted == "true"])
    error_message = "root volumes are encrypted"
  }

  assert {
    condition     = alltrue([for lt in aws_launch_template.node : length(lt.network_interfaces) == 0 && contains(lt.vpc_security_group_ids, "sg-0123456789abcdef0")])
    error_message = "the security group sits at the top level so launches can choose a subnet"
  }

  assert {
    condition     = aws_launch_template.node["frontier"].instance_type == "p5en.48xlarge"
    error_message = "the frontier tier is the 8x H200 node"
  }

  assert {
    condition     = aws_launch_template.node["single-gpu"].image_id == "ami-0123456789abcdef0"
    error_message = "the AMI comes from the SSM parameter by default"
  }
}

run "bootstrap_arms_watchdog_first" {
  command = apply

  assert {
    condition = alltrue([
      for s in values(output.bootstrap_scripts) :
      strcontains(s, "shutdown -h \"+$MINUTES\"") && strcontains(s, "trap finish EXIT")
    ])
    error_message = "every bootstrap arms the shutdown watchdog and powers off on exit"
  }

  assert {
    condition = (
      length(split("shutdown -h \"+$MINUTES\"", output.bootstrap_scripts["frontier"])[0]) <
      length(split("aws s3 cp \"s3://", output.bootstrap_scripts["frontier"])[0])
    )
    error_message = "the watchdog must be armed before the bundle download"
  }

  assert {
    condition     = strcontains(output.bootstrap_scripts["frontier"], "HARD_CAP_HOURS=\"8\"")
    error_message = "the tier hard cap is rendered into the script"
  }
}

run "explicit_ami_and_spot" {
  command = apply

  variables {
    ami_id = "ami-0fedcba9876543210"
    tiers = {
      cheap = { instance_type = "g6.xlarge", root_volume_gb = 100, max_hours = 2, spot = true }
    }
  }

  assert {
    condition     = length(data.aws_ssm_parameter.ami) == 0 && aws_launch_template.node["cheap"].image_id == "ami-0fedcba9876543210"
    error_message = "an explicit AMI skips the SSM lookup"
  }

  assert {
    condition     = aws_launch_template.node["cheap"].instance_market_options[0].market_type == "spot"
    error_message = "spot tiers request one-time spot capacity"
  }
}

run "rejects_long_caps" {
  command = plan

  variables {
    tiers = {
      forever = { instance_type = "p5en.48xlarge", root_volume_gb = 200, max_hours = 72 }
    }
  }

  expect_failures = [var.tiers]
}
