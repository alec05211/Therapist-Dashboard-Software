[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.duckdns\.org$')]
  [string]$DomainName,

  [string]$AwsRegion = "us-east-1"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$dataDirectory = Join-Path $repositoryRoot "terraform\demo"
$organizationDirectory = Join-Path $repositoryRoot "terraform\organizations"
$appDirectory = Join-Path $repositoryRoot "terraform\demo-app"
$destination = Join-Path $appDirectory "terraform.auto.tfvars.json"

function Get-OutputValue([object]$Outputs, [string]$Name) {
  $property = $Outputs.PSObject.Properties[$Name]
  if ($null -eq $property -or $null -eq $property.Value.value) {
    throw "The demo data stack does not expose required output '$Name'. Apply terraform/demo first."
  }
  return $property.Value.value
}

$rawOutputs = & terraform "-chdir=$dataDirectory" output -json
if ($LASTEXITCODE -ne 0) {
  throw "Could not read outputs from terraform/demo. Apply that stack first."
}

$outputs = $rawOutputs | ConvertFrom-Json
$organizationStoragePolicyArns = @()
if (Test-Path $organizationDirectory) {
  $rawOrganizationOutputs = & terraform "-chdir=$organizationDirectory" output -json organization_storage
  if ($LASTEXITCODE -eq 0 -and $rawOrganizationOutputs) {
    $organizationStorage = $rawOrganizationOutputs | ConvertFrom-Json
    $organizationStoragePolicyArns = @(
      $organizationStorage.PSObject.Properties.Value.application_policy_arn |
        Where-Object { $_ } |
        Sort-Object -Unique
    )
  }
}
$configuration = [ordered]@{
  aws_region                              = $AwsRegion
  domain_name                            = $DomainName
  vpc_id                                 = Get-OutputValue $outputs "demo_vpc_id"
  public_subnet_ids                       = @(Get-OutputValue $outputs "demo_public_subnet_ids")
  database_client_security_group_id       = Get-OutputValue $outputs "database_client_security_group_id"
  database_endpoint                       = Get-OutputValue $outputs "database_endpoint"
  database_name                           = Get-OutputValue $outputs "database_name"
  database_secret_arn                     = Get-OutputValue $outputs "database_master_user_secret_arn"
  database_kms_key_arn                    = Get-OutputValue $outputs "database_kms_key_arn"
  hosted_app_runtime_secret_arn           = Get-OutputValue $outputs "hosted_app_runtime_secret_arn"
  healthscribe_input_bucket                = Get-OutputValue $outputs "healthscribe_input_bucket"
  healthscribe_output_bucket               = Get-OutputValue $outputs "healthscribe_output_bucket"
  healthscribe_batch_data_access_role_arn = Get-OutputValue $outputs "healthscribe_batch_data_access_role_arn"
  healthscribe_caller_policy_arn           = Get-OutputValue $outputs "healthscribe_caller_policy_arn"
  organization_storage_policy_arns         = $organizationStoragePolicyArns
}

$json = $configuration | ConvertTo-Json -Depth 4
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($destination, $json, $utf8WithoutBom)
Write-Host "Wrote non-secret demo application identifiers to $destination"
