aws_region = "us-east-1"
project    = "tfm-mlops"
env        = "dev"

cluster_version     = "1.29"
node_instance_types = ["t3.large"]

desired_size = 2
min_size     = 1
max_size     = 3
