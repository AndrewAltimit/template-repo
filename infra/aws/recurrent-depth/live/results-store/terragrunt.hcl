# Results bucket: checkpoints (runs/), node bundles (bundles/), weight mirror (weights/).
include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/results-store"
}

inputs = {
  # RDS_BUCKET_SUFFIX makes the default name globally unique; scripts/infra.sh sets it to the account id.
  name_suffix   = get_env("RDS_BUCKET_SUFFIX", "local")
  force_destroy = include.root.locals.is_emulator
}
