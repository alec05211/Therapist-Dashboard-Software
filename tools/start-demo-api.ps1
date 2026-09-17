[CmdletBinding()]
param(
  [string]$AwsProfile = "terraform",
  [string]$AwsRegion = "us-east-1",
  [ValidateRange(1, 65535)]
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$demoTerraformDirectory = Join-Path $repositoryRoot "terraform\demo"

function Test-TcpPortExclusion([int]$Port) {
  # Windows can reserve ports for services such as Hyper-V or Docker. Uvicorn
  # reports this as WinError 10013, which otherwise looks like a permissions issue.
  $excludedRanges = & netsh interface ipv4 show excludedportrange protocol=tcp
  foreach ($line in $excludedRanges) {
    if ($line -match '^\s*(\d+)\s+(\d+)\s*\*?\s*$') {
      if ($Port -ge [int]$Matches[1] -and $Port -le [int]$Matches[2]) {
        throw "Port $Port is reserved by Windows. Choose a different port with -Port (and set frontend/API_ORIGIN to match), then try again."
      }
    }
  }
}

function Get-ListeningProcessIdsOnPort([int]$Port) {
  # Get-NetTCPConnection can omit listeners owned by another Windows account.
  # netstat still exposes the PID, so use it as the authoritative check.
  $portSuffix = [regex]::Escape(":$Port")
  $processIds = @()
  foreach ($line in (& netstat -ano -p tcp)) {
    if ($line -match "^\s*TCP\s+\S*$portSuffix\s+\S+\s+LISTENING\s+(\d+)\s*$") {
      $processIds += [int]$Matches[1]
    }
  }
  return @($processIds | Select-Object -Unique)
}

function Clear-DashboardApiPort([int]$Port) {
  foreach ($processId in (Get-ListeningProcessIdsOnPort $Port)) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
      continue
    }

    # The dashboard API runs in Python. Do not terminate an unrelated service
    # that happens to use this port.
    if ($process.ProcessName -notin @("python", "pythonw", "uvicorn")) {
      throw "Port $Port is already owned by $($process.ProcessName) (PID $($process.Id)). Stop that application yourself or choose another port with -Port."
    }

    Write-Host "Stopping previous dashboard API process $($process.Id) on port $Port..."
    Stop-Process -Id $process.Id -Force -ErrorAction Stop
  }

  $deadline = (Get-Date).AddSeconds(5)
  while ((Get-Date) -lt $deadline) {
    if (-not (Get-ListeningProcessIdsOnPort $Port)) {
      return
    }
    Start-Sleep -Milliseconds 200
  }

  if (Get-ListeningProcessIdsOnPort $Port) {
    throw "Port $Port did not become available after stopping the prior Python process. Close the process shown by 'netstat -ano -p tcp | Select-String :$Port' and try again."
  }
}

function Test-ApiPortAvailable([int]$Port) {
  Test-TcpPortExclusion $Port
  Clear-DashboardApiPort $Port

  $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
  try {
    $probe.Start()
  } catch {
    throw "Windows could not bind the dashboard API to 127.0.0.1:$Port. $($_.Exception.Message)"
  } finally {
    $probe.Stop()
  }
}

function Get-DemoTerraformOutput([string]$Name) {
  $value = & terraform "-chdir=$demoTerraformDirectory" output -raw $Name
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($value)) {
    throw "Could not read Terraform output '$Name'. Apply the demo stack first."
  }
  return $value.Trim()
}

Push-Location $repositoryRoot
try {
  # Values are process-local: the secret is never written to .env or printed.
  $env:AWS_PROFILE = $AwsProfile
  $env:AWS_REGION = $AwsRegion

  Test-ApiPortAvailable $Port

  $secretArn = Get-DemoTerraformOutput "database_master_user_secret_arn"
  $secretJson = & aws secretsmanager get-secret-value `
    --secret-id $secretArn `
    --query SecretString `
    --output text
  if ($LASTEXITCODE -ne 0) {
    throw "Could not retrieve the demo RDS secret with AWS profile '$AwsProfile'."
  }

  $secret = $secretJson | ConvertFrom-Json
  if ([string]::IsNullOrWhiteSpace($secret.username) -or [string]::IsNullOrWhiteSpace($secret.password)) {
    throw "The RDS secret does not contain a username and password."
  }

  $databaseHost = Get-DemoTerraformOutput "database_endpoint"
  $databaseName = Get-DemoTerraformOutput "database_name"
  $caBundle = Join-Path $env:TEMP "therapist-dashboard-demo-rds-ca.pem"

  Invoke-WebRequest `
    -Uri "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem" `
    -OutFile $caBundle

  $encodedUser = [uri]::EscapeDataString([string]$secret.username)
  $encodedPassword = [uri]::EscapeDataString([string]$secret.password)
  $encodedCaBundle = [uri]::EscapeDataString(($caBundle -replace '\\', '/'))
  $env:DATABASE_URL = (
    "postgresql://{0}:{1}@{2}:5432/{3}?sslmode=verify-full&sslrootcert={4}" -f `
    $encodedUser, $encodedPassword, $databaseHost, $databaseName, $encodedCaBundle
  )

  $env:HEALTHSCRIBE_INPUT_BUCKET = Get-DemoTerraformOutput "healthscribe_input_bucket"
  $env:HEALTHSCRIBE_OUTPUT_BUCKET = Get-DemoTerraformOutput "healthscribe_output_bucket"
  $env:HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN = Get-DemoTerraformOutput "healthscribe_batch_data_access_role_arn"

  & .\.venv\Scripts\python.exe -c "from database.connection import connect; c = connect(); c.close()"
  if ($LASTEXITCODE -ne 0) {
    throw "The demo RDS connection check failed."
  }

  Write-Host "Demo RDS connected. Starting FastAPI on http://127.0.0.1:$Port"
  & .\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --reload --port $Port
} finally {
  Pop-Location
}
