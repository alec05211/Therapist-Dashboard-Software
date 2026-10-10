[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)/32$')]
    [string]$DemoAllowedCidr,

    [ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')]
    [string]$DuckDnsSubdomain = 'therapist-dashboard-demo',

    [string]$Repository = 'alec05211/Therapist-Dashboard-Software'
)

$ErrorActionPreference = 'Stop'

function Invoke-GitHubCli {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & gh @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI command failed: gh $($Arguments -join ' ')"
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI is required. Install it, then run gh auth login.'
}

Invoke-GitHubCli auth status

foreach ($environment in @('demo-app', 'demo-data', 'demo-data-destroy')) {
    Invoke-GitHubCli api --method PUT "repos/$Repository/environments/$environment" | Out-Null
}

$variables = [ordered]@{
    AWS_REGION                   = 'us-east-1'
    TF_STATE_BUCKET              = 'therapist-dashboard-terraform-state-408009925213-us-east-1'
    AWS_TERRAFORM_APP_ROLE_ARN   = 'arn:aws:iam::408009925213:role/therapist-dashboard-demo-app-github'
    AWS_TERRAFORM_DATA_ROLE_ARN  = 'arn:aws:iam::408009925213:role/therapist-dashboard-demo-data-github'
    DUCKDNS_SUBDOMAIN            = $DuckDnsSubdomain
    DEMO_ALLOWED_CIDR            = $DemoAllowedCidr
}

foreach ($entry in $variables.GetEnumerator()) {
    Invoke-GitHubCli variable set $entry.Key --repo $Repository --body $entry.Value
}

$secureToken = Read-Host 'DuckDNS token (input is hidden)' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)

try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    if ([string]::IsNullOrWhiteSpace($plainToken)) {
        throw 'DuckDNS token cannot be empty.'
    }

    $plainToken | gh secret set DUCKDNS_TOKEN --repo $Repository --env demo-app
    if ($LASTEXITCODE -ne 0) {
        throw 'GitHub CLI could not save DUCKDNS_TOKEN in the demo-app environment.'
    }
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    Remove-Variable plainToken -ErrorAction SilentlyContinue
    Remove-Variable secureToken -ErrorAction SilentlyContinue
}

Write-Host 'GitHub environments, repository variables, and the demo-app DuckDNS secret are configured.'
Write-Host 'Add a required reviewer to demo-data-destroy in GitHub Settings before using the destroy operation.'
