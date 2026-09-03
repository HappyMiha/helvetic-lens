param(
    [string]$ModelId = "apertus-1.5b-q4km",
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"
$arguments = @("compose", "up", "--build", "-d")
if (-not $SkipPull) {
    $arguments += "--pull"
    $arguments += "always"
}
$arguments += "model-manager"
docker @arguments

$manager = "http://127.0.0.1:12436"
$ready = $false
for ($attempt = 1; $attempt -le 60; $attempt += 1) {
    try {
        $health = Invoke-RestMethod -Uri "$manager/health" -TimeoutSec 3
        if ($health.status -eq "ok") {
            $ready = $true
            break
        }
    }
    catch {
        if ($attempt % 10 -eq 0) {
            Write-Output "Waiting for the private model manager..."
        }
    }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    throw "The local model manager did not become ready. Inspect: docker compose logs model-manager"
}

$inventory = Invoke-RestMethod -Uri "$manager/v1/inventory"
$model = $inventory.models | Where-Object { $_.id -eq $ModelId }
if (-not $model) {
    throw "Model '$ModelId' is not in the versioned allowlist."
}
Invoke-RestMethod -Method Post -Uri "$manager/v1/models/$ModelId/license" `
    -ContentType "application/json" -Body '{"accepted":true}' | Out-Null

if (-not $model.installed) {
    $cached = if ($model.download.cached_copy_available) { "true" } else { "false" }
    Invoke-RestMethod -Method Post -Uri "$manager/v1/models/$ModelId/download?cached=$cached" | Out-Null
    do {
        Start-Sleep -Seconds 2
        $inventory = Invoke-RestMethod -Uri "$manager/v1/inventory"
        $model = $inventory.models | Where-Object { $_.id -eq $ModelId }
        $percent = [math]::Round(100 * $model.download.downloaded_bytes / $model.download.total_bytes, 1)
        Write-Output "Model state: $($model.state), $percent%"
        if ($model.state -eq "error") { throw $model.error }
    } until ($model.installed)
}

Invoke-RestMethod -Method Post -Uri "$manager/v1/models/$ModelId/start" | Out-Null
do {
    Start-Sleep -Seconds 2
    $inventory = Invoke-RestMethod -Uri "$manager/v1/inventory"
    $model = $inventory.models | Where-Object { $_.id -eq $ModelId }
    if ($model.state -in @("error", "degraded")) { throw $model.error }
} until ($model.state -eq "ready")

$request = @{
    model = $model.served_model_id
    messages = @(
        @{ role = "system"; content = "Return only a valid JSON object. Do not add prose or Markdown." },
        @{ role = "user"; content = 'Return exactly this JSON object: {"status":"ok"}' }
    )
    response_format = @{ type = "json_object" }
    temperature = 0
    max_tokens = 80
    stream = $false
} | ConvertTo-Json -Depth 6
$response = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:12436/openai/v1/chat/completions" `
    -ContentType "application/json" -Body $request -TimeoutSec 180
$parsed = $response.choices[0].message.content | ConvertFrom-Json
if ($parsed.status -ne "ok") {
    throw "Local Apertus returned unexpected structured JSON."
}

Write-Output "Helvetic Lens local Apertus returned valid structured JSON."
Write-Output "Selected artifact: $ModelId ($($model.quantization)); SHA-256 verified."
Write-Output "Open Local models in Helvetic Lens to inspect or change the active model."
