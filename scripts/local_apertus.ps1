param([switch]$SkipPull)

$ErrorActionPreference = "Stop"

$composeArguments = @("compose", "--profile", "local-ai", "up", "-d")
if (-not $SkipPull) {
    $composeArguments += "--pull"
    $composeArguments += "always"
}
$composeArguments += "local-apertus"
docker @composeArguments

$ready = $false
for ($attempt = 1; $attempt -le 180; $attempt += 1) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:12435/health" -TimeoutSec 3
        if ($health.status -eq "ok") {
            $ready = $true
            break
        }
    }
    catch {
        if ($attempt % 10 -eq 0) {
            Write-Output "Waiting for the local Apertus model to download and load..."
        }
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    throw "Local Apertus did not become ready. Inspect: docker compose logs local-apertus"
}

$properties = Invoke-RestMethod -Uri "http://127.0.0.1:12435/props" -TimeoutSec 5
if ($properties.total_slots -ne 1 -or $properties.default_generation_settings.n_ctx -lt 4096) {
    throw "Local Apertus is running with an unsafe context allocation. Recreate it with: docker compose --profile local-ai up -d --force-recreate local-apertus"
}

$request = @{
    model = "local-apertus"
    messages = @(
        @{
            role = "system"
            content = "Return only a valid JSON object. Do not add prose or Markdown."
        },
        @{
            role = "user"
            content = 'Return exactly this JSON object: {"status":"ok"}'
        }
    )
    response_format = @{
        type = "json_object"
    }
    temperature = 0
    max_tokens = 80
    stream = $false
} | ConvertTo-Json -Depth 6

$response = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:12435/v1/chat/completions" `
    -ContentType "application/json" `
    -Body $request `
    -TimeoutSec 180

$content = $response.choices[0].message.content
try {
    $parsed = $content | ConvertFrom-Json
}
catch {
    throw "Local Apertus returned invalid structured JSON: $content"
}

if ($parsed.status -ne "ok") {
    throw "Local Apertus returned unexpected structured JSON: $content"
}

Write-Output "Helvetic Lens local Apertus returned valid structured JSON."
Write-Output "The local runner has one 4,096-token slot, so a full request keeps the complete KV cache."
Write-Output "Open Helvetic Lens Settings and choose Local Docker Apertus to use this model."
