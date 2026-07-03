param(
  [string]$BaseUrl = "http://127.0.0.1:1234/v1",
  [string]$Model = "",
  [string]$ApiKey = "",
  [int]$TimeoutSec = 300,
  [int]$MaxTokens = 512,
  [string]$OutputDir = ".\8060s_smoke_results",
  [switch]$SkipVision
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

try {
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
}

function Join-Url {
  param([string]$Base, [string]$Path)
  return $Base.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Get-ErrorText {
  param($ErrorRecord)

  $message = $ErrorRecord.Exception.Message
  $response = $ErrorRecord.Exception.Response
  if ($null -ne $response) {
    try {
      $stream = $response.GetResponseStream()
      if ($null -ne $stream) {
        $reader = [System.IO.StreamReader]::new($stream)
        $body = $reader.ReadToEnd()
        if (-not [string]::IsNullOrWhiteSpace($body)) {
          $message = "$message`n$body"
        }
      }
    } catch {
      # Keep the original exception message.
    }
  }
  return $message
}

function Invoke-OpenAIJson {
  param(
    [ValidateSet("GET", "POST")]
    [string]$Method,
    [string]$Url,
    $Body = $null,
    [int]$TimeoutSeconds = 300
  )

  $headers = @{}
  if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $headers["Authorization"] = "Bearer $ApiKey"
  }

  $params = @{
    Uri = $Url
    Method = $Method
    TimeoutSec = $TimeoutSeconds
    Headers = $headers
  }

  if ($null -ne $Body) {
    $params["ContentType"] = "application/json; charset=utf-8"
    $params["Body"] = ($Body | ConvertTo-Json -Depth 30 -Compress)
  }

  return Invoke-RestMethod @params
}

function New-TestImageDataUrl {
  $bitmap = $null
  $graphics = $null
  $ms = $null
  try {
    Add-Type -AssemblyName System.Drawing
    $bitmap = [System.Drawing.Bitmap]::new(900, 420)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([System.Drawing.Color]::White)

    $titleFont = [System.Drawing.Font]::new("Arial", 34, [System.Drawing.FontStyle]::Bold)
    $bodyFont = [System.Drawing.Font]::new("Arial", 24, [System.Drawing.FontStyle]::Regular)
    $black = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::Black)
    $blue = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::RoyalBlue)
    $red = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::Crimson)
    $greenPen = [System.Drawing.Pen]::new([System.Drawing.Color]::SeaGreen, 12)

    $graphics.DrawString("8060S VISION TEST 73", $titleFont, $black, 40, 35)
    $graphics.FillRectangle($blue, 70, 150, 220, 120)
    $graphics.FillEllipse($red, 360, 145, 140, 140)
    $graphics.DrawRectangle($greenPen, 585, 145, 210, 120)
    $graphics.DrawString("blue rectangle", $bodyFont, $black, 70, 295)
    $graphics.DrawString("red circle", $bodyFont, $black, 360, 295)
    $graphics.DrawString("green outline", $bodyFont, $black, 585, 295)

    $ms = [System.IO.MemoryStream]::new()
    $bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $base64 = [Convert]::ToBase64String($ms.ToArray())
    return "data:image/png;base64,$base64"
  } finally {
    if ($null -ne $graphics) { $graphics.Dispose() }
    if ($null -ne $bitmap) { $bitmap.Dispose() }
    if ($null -ne $ms) { $ms.Dispose() }
  }
}

function Get-ResponseText {
  param($Response)

  if ($null -eq $Response -or $null -eq $Response.choices -or $Response.choices.Count -lt 1) {
    return ""
  }

  $message = $Response.choices[0].message
  if ($null -eq $message) {
    return ""
  }

  $content = $message.content
  if ($content -is [array]) {
    return ($content | ForEach-Object {
      if ($_.text) { $_.text } else { $_ | ConvertTo-Json -Depth 10 -Compress }
    }) -join "`n"
  }

  if ($null -eq $content) {
    return ""
  }

  return [string]$content
}

function Get-ReasoningText {
  param($Response)

  if ($null -eq $Response -or $null -eq $Response.choices -or $Response.choices.Count -lt 1) {
    return ""
  }

  $message = $Response.choices[0].message
  if ($null -eq $message) {
    return ""
  }

  $reasoning = $message.reasoning_content
  if ($null -eq $reasoning) {
    return ""
  }

  return [string]$reasoning
}

function Add-Result {
  param($Result)
  $script:Results.Add([pscustomobject]$Result) | Out-Null
}

function Save-RawResponse {
  param([string]$Id, $Response)
  $rawPath = Join-Path $script:RawDir "$Id.json"
  $Response | ConvertTo-Json -Depth 40 | Set-Content -Path $rawPath -Encoding UTF8
}

function Invoke-ChatCase {
  param(
    [string]$Id,
    [string]$Name,
    $Messages,
    [int]$CaseMaxTokens = 512,
    [double]$Temperature = 0.2,
    [string]$ExpectRegex = "",
    [int]$CaseTimeoutSec = 300
  )

  $body = [ordered]@{
    model = $script:SelectedModel
    messages = $Messages
    max_tokens = $CaseMaxTokens
    temperature = $Temperature
    stream = $false
  }

  Write-Host "Running $Id - $Name ..."
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $response = Invoke-OpenAIJson -Method POST -Url (Join-Url $BaseUrl "chat/completions") -Body $body -TimeoutSeconds $CaseTimeoutSec
    $sw.Stop()
    Save-RawResponse -Id $Id -Response $response

    $content = Get-ResponseText -Response $response
    $reasoning = Get-ReasoningText -Response $response
    $finishReason = ""
    if ($response.choices.Count -gt 0) {
      $finishReason = [string]$response.choices[0].finish_reason
    }

    $contentNonEmpty = -not [string]::IsNullOrWhiteSpace($content)
    $regexPassed = $true
    if (-not [string]::IsNullOrWhiteSpace($ExpectRegex)) {
      $regexPassed = $content -match $ExpectRegex
    }

    $passed = $contentNonEmpty -and $regexPassed -and ($finishReason -ne "length")
    Add-Result @{
      id = $Id
      name = $Name
      ok = $true
      passed = $passed
      latency_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      finish_reason = $finishReason
      content_length = $content.Length
      reasoning_length = $reasoning.Length
      prompt_tokens = $response.usage.prompt_tokens
      completion_tokens = $response.usage.completion_tokens
      total_tokens = $response.usage.total_tokens
      expect_regex = $ExpectRegex
      content_preview = $content.Substring(0, [Math]::Min(700, $content.Length))
      error = ""
    }
  } catch {
    $sw.Stop()
    Add-Result @{
      id = $Id
      name = $Name
      ok = $false
      passed = $false
      latency_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      finish_reason = ""
      content_length = 0
      reasoning_length = 0
      prompt_tokens = $null
      completion_tokens = $null
      total_tokens = $null
      expect_regex = $ExpectRegex
      content_preview = ""
      error = Get-ErrorText -ErrorRecord $_
    }
  }
}

$runId = Get-Date -Format "yyyyMMdd_HHmmss"
$root = Resolve-Path "."
$resolvedOutputDir = $OutputDir
if (-not [System.IO.Path]::IsPathRooted($resolvedOutputDir)) {
  $resolvedOutputDir = Join-Path $root $OutputDir
}
$runDir = Join-Path $resolvedOutputDir "8060s_smoke_$runId"
$script:RawDir = Join-Path $runDir "raw"
New-Item -ItemType Directory -Force -Path $script:RawDir | Out-Null

$script:Results = [System.Collections.Generic.List[object]]::new()
$modelsUrl = Join-Url $BaseUrl "models"

Write-Host "8060S brain smoke test"
Write-Host "BaseUrl: $BaseUrl"
Write-Host "Output:  $runDir"

$systemInfo = [ordered]@{
  run_id = $runId
  started_at = (Get-Date).ToString("o")
  computer_name = $env:COMPUTERNAME
  user_name = $env:USERNAME
  powershell = $PSVersionTable.PSVersion.ToString()
  base_url = $BaseUrl
  api_key_provided = -not [string]::IsNullOrWhiteSpace($ApiKey)
}

try {
  $os = Get-CimInstance Win32_OperatingSystem
  $cs = Get-CimInstance Win32_ComputerSystem
  $gpu = Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, DriverDate
  $systemInfo["os"] = $os.Caption
  $systemInfo["total_physical_memory_gb"] = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
  $systemInfo["gpu"] = $gpu
} catch {
  $systemInfo["system_info_error"] = $_.Exception.Message
}

try {
  $modelsResponse = Invoke-OpenAIJson -Method GET -Url $modelsUrl -TimeoutSeconds 30
  Save-RawResponse -Id "t00_models" -Response $modelsResponse

  $modelIds = @($modelsResponse.data | ForEach-Object { [string]$_.id })
  if ($modelIds.Count -eq 0) {
    throw "No models returned from $modelsUrl"
  }

  if ([string]::IsNullOrWhiteSpace($Model)) {
    $preferred = @($modelIds | Where-Object { $_ -match "35|3\.6|a3b|qwen" } | Select-Object -First 1)
    if ($preferred.Count -gt 0) {
      $script:SelectedModel = $preferred[0]
    } else {
      $script:SelectedModel = $modelIds[0]
    }
  } else {
    $script:SelectedModel = $Model
  }

  $systemInfo["available_models"] = $modelIds
  $systemInfo["selected_model"] = $script:SelectedModel

  Add-Result @{
    id = "t00_models"
    name = "GET /v1/models"
    ok = $true
    passed = $true
    latency_seconds = $null
    finish_reason = ""
    content_length = 0
    reasoning_length = 0
    prompt_tokens = $null
    completion_tokens = $null
    total_tokens = $null
    expect_regex = ""
    content_preview = "Models: " + ($modelIds -join ", ")
    error = ""
  }
} catch {
  Add-Result @{
    id = "t00_models"
    name = "GET /v1/models"
    ok = $false
    passed = $false
    latency_seconds = $null
    finish_reason = ""
    content_length = 0
    reasoning_length = 0
    prompt_tokens = $null
    completion_tokens = $null
    total_tokens = $null
    expect_regex = ""
    content_preview = ""
    error = Get-ErrorText -ErrorRecord $_
  }

  $report = [ordered]@{
    system = $systemInfo
    results = $script:Results
  }
  $jsonPath = Join-Path $runDir "8060s_smoke_report.json"
  $report | ConvertTo-Json -Depth 50 | Set-Content -Path $jsonPath -Encoding UTF8
  Write-Host "Model endpoint failed. Report written to $jsonPath"
  exit 1
}

$systemPrompt = "You are being tested as a local LabAgent brain candidate. Put final answer in message.content. Do not hide the final answer in reasoning_content. Be concise and concrete."

Invoke-ChatCase `
  -Id "t01_short_en" `
  -Name "short exact answer" `
  -Messages @(
    @{ role = "system"; content = $systemPrompt },
    @{ role = "user"; content = "Reply with exactly: brain-ok" }
  ) `
  -CaseMaxTokens 64 `
  -Temperature 0.0 `
  -ExpectRegex "brain-ok" `
  -CaseTimeoutSec 180

Invoke-ChatCase `
  -Id "t02_short_zh" `
  -Name "Chinese final content" `
  -Messages @(
    @{ role = "system"; content = $systemPrompt },
    @{ role = "user"; content = "只用一句中文回答：你现在是在 8060S 候选节点上接受本地模型测试。不要输出思考过程。" }
  ) `
  -CaseMaxTokens 128 `
  -Temperature 0.2 `
  -ExpectRegex "8060S|候选|本地|模型" `
  -CaseTimeoutSec 180

Invoke-ChatCase `
  -Id "t03_code_review" `
  -Name "small code reasoning" `
  -Messages @(
    @{ role = "system"; content = $systemPrompt },
    @{ role = "user"; content = @'
Read this Python code and answer in 3 short bullet points:

def format_total(cents):
    return "$" + str(cents / 100)

Include: what it does, one bug or quality issue, and a better implementation.
'@ }
  ) `
  -CaseMaxTokens $MaxTokens `
  -Temperature 0.2 `
  -ExpectRegex "format_total|cents|100|format|round" `
  -CaseTimeoutSec $TimeoutSec

Invoke-ChatCase `
  -Id "t04_labagent_arch" `
  -Name "LabAgent architecture recommendation" `
  -Messages @(
    @{ role = "system"; content = $systemPrompt },
    @{ role = "user"; content = "LabAgent 当前有 5090 跑 qwen-agent，新设备跑 embed-local/vision-local，8060S 是新恢复的候选节点。请用 5 条以内建议说明 8060S 应该先承担什么角色，为什么不要直接替换 5090 主代码模型。" }
  ) `
  -CaseMaxTokens $MaxTokens `
  -Temperature 0.3 `
  -ExpectRegex "5090|8060S|qwen-agent|benchmark|候选" `
  -CaseTimeoutSec $TimeoutSec

Invoke-ChatCase `
  -Id "t05_long_zh" `
  -Name "300-500 Chinese chars stability" `
  -Messages @(
    @{ role = "system"; content = $systemPrompt },
    @{ role = "user"; content = "请用 300 到 500 字解释：为什么一个 reasoning 模型在成为团队默认 coding worker 前，必须先通过 latency、content 非空率、patch、repo map、Codex smoke 和稳定性测试。要求最终答案必须直接写在 content 里，不要只写思考过程。" }
  ) `
  -CaseMaxTokens ([Math]::Max($MaxTokens, 768)) `
  -Temperature 0.3 `
  -ExpectRegex "latency|content|patch|Codex|稳定|测试|benchmark" `
  -CaseTimeoutSec ([Math]::Max($TimeoutSec, 420))

if ($SkipVision) {
  Add-Result @{
    id = "t06_vision"
    name = "vision image smoke"
    ok = $true
    passed = $true
    latency_seconds = $null
    finish_reason = "skipped"
    content_length = 0
    reasoning_length = 0
    prompt_tokens = $null
    completion_tokens = $null
    total_tokens = $null
    expect_regex = ""
    content_preview = "Skipped by -SkipVision"
    error = ""
  }
} else {
  try {
    $imageUrl = New-TestImageDataUrl
    Invoke-ChatCase `
      -Id "t06_vision" `
      -Name "vision image smoke" `
      -Messages @(
        @{
          role = "user"
          content = @(
            @{ type = "text"; text = "Read the image. Reply with the visible title text and list the blue/red/green shapes. Keep it short." },
            @{ type = "image_url"; image_url = @{ url = $imageUrl } }
          )
        }
      ) `
      -CaseMaxTokens 256 `
      -Temperature 0.2 `
      -ExpectRegex "8060S|VISION|73|blue|red|green|rectangle|circle" `
      -CaseTimeoutSec ([Math]::Max($TimeoutSec, 420))
  } catch {
    Add-Result @{
      id = "t06_vision"
      name = "vision image smoke"
      ok = $false
      passed = $false
      latency_seconds = $null
      finish_reason = ""
      content_length = 0
      reasoning_length = 0
      prompt_tokens = $null
      completion_tokens = $null
      total_tokens = $null
      expect_regex = "8060S|VISION|73|blue|red|green|rectangle|circle"
      content_preview = ""
      error = Get-ErrorText -ErrorRecord $_
    }
  }
}

$passedCount = @($script:Results | Where-Object { $_.passed }).Count
$totalCount = $script:Results.Count
$failedCount = $totalCount - $passedCount
$systemInfo["finished_at"] = (Get-Date).ToString("o")
$systemInfo["passed"] = $passedCount
$systemInfo["failed"] = $failedCount
$systemInfo["total"] = $totalCount

$report = [ordered]@{
  system = $systemInfo
  results = $script:Results
}

$jsonPath = Join-Path $runDir "8060s_smoke_report.json"
$mdPath = Join-Path $runDir "8060s_smoke_report.md"
$report | ConvertTo-Json -Depth 50 | Set-Content -Path $jsonPath -Encoding UTF8

$md = [System.Collections.Generic.List[string]]::new()
$md.Add("# 8060S Brain Smoke Report") | Out-Null
$md.Add("") | Out-Null
$md.Add("- Run ID: $runId") | Out-Null
$md.Add("- Base URL: $BaseUrl") | Out-Null
$md.Add(("- Selected model: {0}" -f $systemInfo["selected_model"])) | Out-Null
$md.Add("- Passed: $passedCount / $totalCount") | Out-Null
$md.Add("- TimeoutSec: $TimeoutSec") | Out-Null
$md.Add("- MaxTokens: $MaxTokens") | Out-Null
$md.Add("") | Out-Null
$md.Add("## Results") | Out-Null
$md.Add("") | Out-Null
$md.Add("| ID | Passed | OK | Latency(s) | Finish | Content | Reasoning | Tokens | Note |") | Out-Null
$md.Add("|----|--------|----|------------|--------|---------|-----------|--------|------|") | Out-Null
foreach ($r in $script:Results) {
  $note = ""
  if (-not [string]::IsNullOrWhiteSpace($r.error)) {
    $note = ($r.error -replace "`r?`n", " ") -replace "\|", "/"
    if ($note.Length -gt 120) { $note = $note.Substring(0, 120) + "..." }
  } else {
    $note = ($r.content_preview -replace "`r?`n", " ") -replace "\|", "/"
    if ($note.Length -gt 120) { $note = $note.Substring(0, 120) + "..." }
  }
  $md.Add("| $($r.id) | $($r.passed) | $($r.ok) | $($r.latency_seconds) | $($r.finish_reason) | $($r.content_length) | $($r.reasoning_length) | $($r.total_tokens) | $note |") | Out-Null
}

$md.Add("") | Out-Null
$md.Add("## How To Read") | Out-Null
$md.Add("") | Out-Null
$md.Add("- `content_length=0` means the model may be stuck in reasoning-only output for OpenAI-compatible clients.") | Out-Null
$md.Add("- `finish=length` means the output budget was exhausted; lower context or max tokens before using it as a route.") | Out-Null
$md.Add("- Vision failure is acceptable if this model is only meant to be `brain-local`, but it should not replace `vision-local`.") | Out-Null
$md.Add("- Send this whole result folder back for review, especially `8060s_smoke_report.json` and `8060s_smoke_report.md`.") | Out-Null

$md | Set-Content -Path $mdPath -Encoding UTF8

Write-Host ""
Write-Host "Done."
Write-Host "Passed: $passedCount / $totalCount"
Write-Host "Markdown report: $mdPath"
Write-Host "JSON report:     $jsonPath"
Write-Host "Raw responses:   $script:RawDir"

if ($failedCount -gt 0) {
  exit 2
}

exit 0
