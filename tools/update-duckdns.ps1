[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')]
  [string]$Subdomain,

  [Parameter(Mandatory = $true)]
  [ValidateScript({
    $parsed = [System.Net.IPAddress]::None
    [System.Net.IPAddress]::TryParse($_, [ref]$parsed) -and $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
  })]
  [string]$IpAddress
)

$ErrorActionPreference = "Stop"
$token = $env:DUCKDNS_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) {
  throw "Set DUCKDNS_TOKEN in the current process before updating DNS."
}

$uri = "https://www.duckdns.org/update?domains=$([uri]::EscapeDataString($Subdomain))&token=$([uri]::EscapeDataString($token))&ip=$([uri]::EscapeDataString($IpAddress))"
$response = Invoke-RestMethod -Method Get -Uri $uri
if ([string]$response -ne "OK") {
  throw "DuckDNS rejected the update."
}

Write-Host "Updated $Subdomain.duckdns.org to $IpAddress."
