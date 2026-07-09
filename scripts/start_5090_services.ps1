param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("qwen-tunnel", "rag", "rag-tunnel", "agent", "agent-tunnel", "status")]
    [string]$Action,

    [string]$RepoRoot = "E:\qwen_setup",
    [string]$CloudHost = "82.156.69.153",
    [string]$CloudUser = "ubuntu",
    [string]$SshKey = "C:\Users\N\.ssh\id_ed25519"
)

$ErrorActionPreference = "Stop"

function Import-LabAgentEnv {
    param([string]$Root)

    $envPath = Join-Path $Root ".env.local"
    if (-not (Test-Path $envPath)) {
        throw "Missing .env.local at $envPath"
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

function Show-Status {
    Write-Host "Local listeners:"
    netstat -ano | findstr ":1234 :8010 :8020"

    Write-Host ""
    Write-Host "Cloud listeners:"
    ssh "$CloudUser@$CloudHost" "sudo ss -ltnp | egrep ':8000|:12340|:12341|:18010|:18020' || true"
}

Set-Location $RepoRoot

switch ($Action) {
    "qwen-tunnel" {
        Write-Host "Starting 5090 LM Studio reverse tunnel: cloud :12340 -> 127.0.0.1:1234"
        ssh -N -R 12340:127.0.0.1:1234 -i $SshKey `
            -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
            "$CloudUser@$CloudHost"
    }

    "rag" {
        Import-LabAgentEnv -Root $RepoRoot
        Write-Host "Starting RAG Service on http://127.0.0.1:8010"
        python -m services.rag.server --host 127.0.0.1 --port 8010
    }

    "rag-tunnel" {
        Write-Host "Starting RAG reverse tunnel: cloud :18010 -> 127.0.0.1:8010"
        ssh -N -R 0.0.0.0:18010:127.0.0.1:8010 -i $SshKey `
            -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
            "$CloudUser@$CloudHost"
    }

    "agent" {
        Import-LabAgentEnv -Root $RepoRoot
        Write-Host "Starting Agent Router on http://127.0.0.1:8020"
        Write-Host "Using base URL: $env:LABAGENT_BASE_URL"
        python -m services.agent.server `
            --host 127.0.0.1 `
            --port 8020 `
            --base-url $env:LABAGENT_BASE_URL `
            --api-key $env:LABAGENT_API_KEY `
            --chat-model qwen-agent `
            --vision-model vision-local `
            --agent-model labagent-agent `
            --rag-base-url http://127.0.0.1:8010 `
            --rag-api-key $env:LABAGENT_RAG_API_KEY `
            --service-api-key $env:LABAGENT_AGENT_API_KEY
    }

    "agent-tunnel" {
        Write-Host "Starting Agent Router reverse tunnel: cloud :18020 -> 127.0.0.1:8020"
        ssh -N -R 0.0.0.0:18020:127.0.0.1:8020 -i $SshKey `
            -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
            "$CloudUser@$CloudHost"
    }

    "status" {
        Show-Status
    }
}
