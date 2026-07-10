param(
    [string]$RepoRoot = "E:\qwen_setup",
    [string]$CloudHost = "82.156.69.153",
    [string]$CloudUser = "ubuntu",
    [int]$TimeoutSec = 20,
    [switch]$SkipSsh,
    [switch]$SkipVision,
    [switch]$NoLog
)

$ErrorActionPreference = "Continue"

$Checks = New-Object System.Collections.Generic.List[object]
$CloudListeners = ""

function Import-LabAgentEnv {
    param([string]$Root)

    $envPath = Join-Path $Root ".env.local"
    if (-not (Test-Path $envPath)) {
        Add-Check "env.local" "config" "FAIL" "Missing $envPath" "Run from the LabAgent repo or pass -RepoRoot."
        return
    }

    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") {
            return
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
        }
    }
}

function Add-Check {
    param(
        [string]$Name,
        [string]$Layer,
        [ValidateSet("OK", "WARN", "FAIL")]
        [string]$Status,
        [string]$Detail,
        [string]$Hint = ""
    )

    $script:Checks.Add([pscustomobject]@{
        name = $Name
        layer = $Layer
        status = $Status
        detail = $Detail
        hint = $Hint
    }) | Out-Null
}

function Test-RequiredEnv {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ([string]::IsNullOrWhiteSpace($value)) {
            Add-Check $name "config" "FAIL" "Missing required environment value." "Check .env.local on 5090."
        }
    }
}

function Test-LocalPort {
    param(
        [int]$Port,
        [string]$Name,
        [string]$Hint
    )

    $lines = netstat -ano | Select-String (":$Port\s+.*LISTENING")
    if ($lines) {
        $pids = @()
        foreach ($line in $lines) {
            $parts = $line.ToString().Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
            $pids += $parts[-1]
        }
        Add-Check $Name "local" "OK" "Listening on 127.0.0.1:$Port; pid(s): $($pids -join ', ')." ""
    }
    else {
        Add-Check $Name "local" "FAIL" "No local listener on port $Port." $Hint
    }
}

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [int]$Timeout = 20
    )

    try {
        if ($null -eq $Body) {
            $result = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -TimeoutSec $Timeout
        }
        else {
            $json = $Body | ConvertTo-Json -Depth 20
            $result = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -ContentType "application/json; charset=utf-8" -Body $json -TimeoutSec $Timeout
        }
        return [pscustomobject]@{ ok = $true; data = $result; error = "" }
    }
    catch {
        $message = $_.Exception.Message
        $bodyText = ""
        try {
            if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $bodyText = $reader.ReadToEnd()
            }
        }
        catch {
            $bodyText = ""
        }
        if ($bodyText) {
            $message = "$message | $bodyText"
        }
        return [pscustomobject]@{ ok = $false; data = $null; error = $message }
    }
}

function Test-CloudPort {
    param(
        [int]$Port,
        [string]$Name,
        [string]$StatusIfMissing = "FAIL",
        [string]$Hint = ""
    )

    if ($SkipSsh) {
        Add-Check $Name "cloud" "WARN" "Skipped SSH listener check." "Run without -SkipSsh for full tunnel visibility."
        return
    }

    if ($script:CloudListeners -match ":$Port\s") {
        Add-Check $Name "cloud" "OK" "Cloud is listening on port $Port." ""
    }
    else {
        Add-Check $Name "cloud" $StatusIfMissing "Cloud is not listening on port $Port." $Hint
    }
}

function Get-CloudListeners {
    if ($SkipSsh) {
        return
    }

    try {
        $script:CloudListeners = ssh "$CloudUser@$CloudHost" "sudo ss -ltnp | egrep ':8000|:12340|:12341|:12342|:18010|:18020' || true"
    }
    catch {
        Add-Check "cloud ssh" "cloud" "FAIL" "Cannot run ssh listener check: $($_.Exception.Message)" "Check SSH auth to $CloudUser@$CloudHost."
        $script:CloudListeners = ""
    }
}

function Show-Summary {
    $ordered = $Checks | Sort-Object layer, name
    $ordered | Format-Table status, layer, name, detail -AutoSize

    $failed = @($Checks | Where-Object { $_.status -eq "FAIL" })
    $warned = @($Checks | Where-Object { $_.status -eq "WARN" })

    Write-Host ""
    Write-Host "Summary:"
    Write-Host "  OK:   $(($Checks | Where-Object { $_.status -eq 'OK' }).Count)"
    Write-Host "  WARN: $($warned.Count)"
    Write-Host "  FAIL: $($failed.Count)"

    if ($failed.Count -gt 0 -or $warned.Count -gt 0) {
        Write-Host ""
        Write-Host "Next actions:"
        foreach ($check in @($failed + $warned)) {
            if ($check.hint) {
                Write-Host "  [$($check.status)] $($check.name): $($check.hint)"
            }
        }
    }

    if ($failed.Count -eq 0) {
        Write-Host ""
        Write-Host "Overall: core LabAgent route is usable."
    }
    else {
        Write-Host ""
        Write-Host "Overall: attention required."
    }
}

Set-Location $RepoRoot
Import-LabAgentEnv -Root $RepoRoot
Test-RequiredEnv @("LABAGENT_API_KEY", "LABAGENT_BASE_URL", "LABAGENT_RAG_API_KEY", "LABAGENT_AGENT_API_KEY")

Write-Host "LabAgent full-link status check"
Write-Host "Repo: $RepoRoot"
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
Write-Host ""

Test-LocalPort 1234 "5090 LM Studio" "Start LM Studio Local Server on 5090."
Test-LocalPort 8010 "RAG Service" ".\scripts\start_5090_services.ps1 -Action rag"
Test-LocalPort 8020 "Agent Router" ".\scripts\start_5090_services.ps1 -Action agent"

Get-CloudListeners
Test-CloudPort 8000 "LiteLLM gateway" "FAIL" "Restart litellm-gateway on the cloud server."
Test-CloudPort 12340 "5090 qwen tunnel" "FAIL" ".\scripts\start_5090_services.ps1 -Action qwen-tunnel"
Test-CloudPort 12341 "new-device embed/vision tunnel" "FAIL" "Start the :12341 tunnel on the new device."
Test-CloudPort 18010 "public RAG tunnel" "WARN" ".\scripts\start_5090_services.ps1 -Action rag-tunnel"
Test-CloudPort 18020 "public agent tunnel" "FAIL" ".\scripts\start_5090_services.ps1 -Action agent-tunnel"

$mainHeaders = @{ Authorization = "Bearer $env:LABAGENT_API_KEY" }
$ragHeaders = @{ Authorization = "Bearer $env:LABAGENT_RAG_API_KEY" }
$agentHeaders = @{ Authorization = "Bearer $env:LABAGENT_AGENT_API_KEY" }

$models = Invoke-Json "GET" "http://$CloudHost`:8000/v1/models" $mainHeaders $null $TimeoutSec
if ($models.ok) {
    $ids = @($models.data.data | ForEach-Object { $_.id })
    Add-Check "LiteLLM /v1/models" "api" "OK" "Models: $($ids -join ', ')." ""
}
else {
    Add-Check "LiteLLM /v1/models" "api" "FAIL" $models.error "Check :8000, LABAGENT_API_KEY, and LiteLLM service."
}

$chatBody = @{
    model = "qwen-agent"
    messages = @(@{ role = "user"; content = "reply pong only" })
    max_tokens = 20
    temperature = 0
}
$chat = Invoke-Json "POST" "http://$CloudHost`:8000/v1/chat/completions" $mainHeaders $chatBody ([Math]::Max($TimeoutSec, 80))
if ($chat.ok) {
    $content = $chat.data.choices[0].message.content
    Add-Check "qwen-agent chat" "api" "OK" "Content: $content" ""
}
else {
    Add-Check "qwen-agent chat" "api" "FAIL" $chat.error "Check 5090 LM Studio and :12340 tunnel."
}

$embedBody = @{ model = "embed-local"; input = "hello labagent" }
$embed = Invoke-Json "POST" "http://$CloudHost`:8000/v1/embeddings" $mainHeaders $embedBody ([Math]::Max($TimeoutSec, 80))
if ($embed.ok) {
    $dims = $embed.data.data[0].embedding.Count
    Add-Check "embed-local embeddings" "api" "OK" "Dimensions: $dims" ""
}
else {
    Add-Check "embed-local embeddings" "api" "FAIL" $embed.error "Check new-device LM Studio and :12341 tunnel."
}

if (-not $SkipVision) {
    $redPixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8z8BQDwAFgwJ/lh8fqwAAAABJRU5ErkJggg=="
    $visionBody = @{
        model = "vision-local"
        messages = @(@{
            role = "user"
            content = @(
                @{ type = "text"; text = "What is the dominant color? Reply one English word." },
                @{ type = "image_url"; image_url = @{ url = $redPixel } }
            )
        })
        max_tokens = 20
        temperature = 0
    }
    $vision = Invoke-Json "POST" "http://$CloudHost`:8000/v1/chat/completions" $mainHeaders $visionBody ([Math]::Max($TimeoutSec, 120))
    if ($vision.ok) {
        $content = $vision.data.choices[0].message.content
        Add-Check "vision-local image" "api" "OK" "Content: $content" ""
    }
    else {
        Add-Check "vision-local image" "api" "FAIL" $vision.error "Check vision model load and :12341 tunnel."
    }
}
else {
    Add-Check "vision-local image" "api" "WARN" "Skipped vision request." "Run without -SkipVision for full image check."
}

$localRag = Invoke-Json "GET" "http://127.0.0.1:8010/health" $ragHeaders $null $TimeoutSec
if ($localRag.ok) {
    Add-Check "local RAG health" "api" "OK" "Chunks: $($localRag.data.chunk_count); embedding: $($localRag.data.embedding_model)." ""
}
else {
    Add-Check "local RAG health" "api" "FAIL" $localRag.error ".\scripts\start_5090_services.ps1 -Action rag"
}

$publicRag = Invoke-Json "GET" "http://$CloudHost`:18010/health" $ragHeaders $null $TimeoutSec
if ($publicRag.ok) {
    Add-Check "public RAG health" "api" "OK" "Chunks: $($publicRag.data.chunk_count)." ""
}
else {
    Add-Check "public RAG health" "api" "WARN" $publicRag.error ".\scripts\start_5090_services.ps1 -Action rag-tunnel, if public RAG is needed."
}

$agentHealth = Invoke-Json "GET" "http://$CloudHost`:18020/health" $agentHeaders $null $TimeoutSec
if ($agentHealth.ok) {
    Add-Check "labagent-agent health" "api" "OK" "Chat: $($agentHealth.data.chat_model); vision: $($agentHealth.data.vision_model)." ""
}
else {
    Add-Check "labagent-agent health" "api" "FAIL" $agentHealth.error "Check Agent Router :8020 and :18020 tunnel."
}

$agentBody = @{
    model = "labagent-agent"
    messages = @(@{ role = "user"; content = "reply pong only" })
    max_tokens = 20
    temperature = 0
}
$agentChat = Invoke-Json "POST" "http://$CloudHost`:18020/v1/chat/completions" $agentHeaders $agentBody ([Math]::Max($TimeoutSec, 100))
if ($agentChat.ok) {
    $content = $agentChat.data.choices[0].message.content
    $route = $agentChat.data.labagent.route
    $final = $agentChat.data.labagent.final_model
    Add-Check "labagent-agent chat" "api" "OK" "Content: $content; route: $route; final: $final." ""
}
else {
    Add-Check "labagent-agent chat" "api" "FAIL" $agentChat.error "Restart with .\scripts\start_5090_services.ps1 -Action agent, then ensure -Action agent-tunnel is running."
}

Show-Summary

if (-not $NoLog) {
    $logDir = Join-Path $RepoRoot "logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $path = Join-Path $logDir ("labagent_status_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    $payload = [pscustomobject]@{
        created_at = (Get-Date).ToString("s")
        repo_root = $RepoRoot
        cloud_host = $CloudHost
        checks = $Checks
    }
    $payload | ConvertTo-Json -Depth 20 | Set-Content -Path $path -Encoding UTF8
    Write-Host ""
    Write-Host "Wrote log: $path"
}
