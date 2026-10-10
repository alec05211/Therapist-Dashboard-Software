# Terraform bootstrap

This root creates the shared Terraform state bucket and the GitHub Actions OIDC
roles. It is intentionally separate from both application and database state.

The first apply uses local state because an S3 backend cannot create its own
bucket. After the bucket exists, initialize again with `-migrate-state` and the
`therapist-dashboard/bootstrap.tfstate` key. The committed backend block stays
partial so local operators and GitHub Actions can supply the bucket and Region.

The OIDC trust policies accept tokens only from
`alec05211/Therapist-Dashboard-Software` and the named GitHub Environments.
No long-lived AWS access key is stored in GitHub.
