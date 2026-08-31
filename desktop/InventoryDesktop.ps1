$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AppUrl = "http://127.0.0.1:8000"
$MongoExe = Join-Path $Root "mongodb-win32-x86_64-windows-7.0.14\bin\mongod.exe"
$PythonExe = Join-Path $Root "venv\Scripts\python.exe"
$MongoData = Join-Path $Root "data\mongo-db"
$MongoLog = Join-Path $Root "data\mongod-desktop.log"
$DocumentsDir = Join-Path $Root "generated-documents"
$EnvFile = Join-Path $Root ".env"

function Import-EnvFile($Path) {
  if (-not (Test-Path $Path)) {
    return
  }
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $name, $value = $line.Split("=", 2)
    $name = $name.Trim()
    $value = $value.Trim().Trim('"').Trim("'")
    if ($name) {
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

function Ensure-Directory($Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Test-Health {
  try {
    $response = Invoke-WebRequest -UseBasicParsing "$AppUrl/health" -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Start-LocalService($FilePath, $Arguments, $WorkingDirectory) {
  Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden | Out-Null
}

Ensure-Directory $MongoData
Ensure-Directory $DocumentsDir
Import-EnvFile $EnvFile

$MongoUri = if ($env:MONGO_URI) { $env:MONGO_URI } else { "mongodb://127.0.0.1:27017" }
$UseLocalMongo = $MongoUri -match "^mongodb://(localhost|127\.0\.0\.1)(:|/)"

if ($UseLocalMongo -and -not (Test-Path $MongoExe)) {
  throw "MongoDB was not found at $MongoExe"
}

if (-not (Test-Path $PythonExe)) {
  throw "Python was not found at $PythonExe"
}

if (-not (Test-Health)) {
  if ($UseLocalMongo) {
    Start-LocalService $MongoExe @("--dbpath", $MongoData, "--logpath", $MongoLog, "--bind_ip", "127.0.0.1", "--port", "27017") $Root
    Start-Sleep -Seconds 2
  }

  $backendArgs = @("-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000")
  $env:MONGO_URI = $MongoUri
  if (-not $env:MONGO_DB) { $env:MONGO_DB = "inventory_management" }
  if (-not $env:DOCUMENTS_DIR) { $env:DOCUMENTS_DIR = $DocumentsDir }
  if (-not $env:CORS_ORIGINS) { $env:CORS_ORIGINS = $AppUrl }
  Start-LocalService $PythonExe $backendArgs $Root
}

$deadline = (Get-Date).AddSeconds(30)
while (-not (Test-Health)) {
  if ((Get-Date) -gt $deadline) {
    throw "The Inventory application did not start. Please check data\mongod-desktop.log."
  }
  Start-Sleep -Milliseconds 800
}

$edge = @(
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($edge) {
  Start-Process -FilePath $edge -ArgumentList @("--app=$AppUrl")
} elseif ($chrome) {
  Start-Process -FilePath $chrome -ArgumentList @("--app=$AppUrl")
} else {
  Start-Process $AppUrl
}
