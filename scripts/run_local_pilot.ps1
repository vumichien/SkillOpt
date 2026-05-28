#!/usr/bin/env pwsh
# Launch the mcqa local pilot: DeepSeek optimizer (cloud) + local Qwen2.5-7B target (Ollama).
# Resume-aware: re-running continues the same outputs/mcqa_local_pilot run.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 1. Load .env.local-pilot if present
$EnvFile = Join-Path $ProjectRoot ".env.local-pilot"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $key = $line.Substring(0, $idx).Trim()
            $val = $line.Substring($idx + 1).Trim()
            Set-Item -Path "Env:$key" -Value $val
        }
    }
    Write-Host "[pilot] loaded $EnvFile"
} else {
    Write-Host "[pilot] no .env.local-pilot found; relying on current environment"
}

# 2. Fail fast if the DeepSeek optimizer key is missing
if (-not $env:OPTIMIZER_OPENAI_API_KEY) {
    Write-Error "OPTIMIZER_OPENAI_API_KEY is not set. Copy .env.local-pilot.example to .env.local-pilot and fill it in."
    exit 1
}

# 3. Ensure Ollama is up and the target model is pulled + warm
$Model = if ($env:TARGET_DEPLOYMENT) { $env:TARGET_DEPLOYMENT } else { "qwen2.5:7b-instruct-q4_K_M" }
$OllamaBase = if ($env:QWEN_CHAT_BASE_URL) { $env:QWEN_CHAT_BASE_URL } else { "http://localhost:11434/v1" }
try {
    Invoke-RestMethod -Uri "$OllamaBase/models" -TimeoutSec 10 | Out-Null
} catch {
    Write-Error "Ollama not reachable at $OllamaBase. Start it with 'ollama serve'."
    exit 1
}
$tags = (& ollama list) 2>$null
if (-not ($tags -match [regex]::Escape($Model))) {
    Write-Host "[pilot] pulling $Model ..."
    & ollama pull $Model
}

# 4. Run training (PYTHONUTF8 guards config loading on non-UTF8 consoles)
$env:PYTHONUTF8 = "1"
$OutRoot = if ($env:SKILLOPT_OUT_ROOT) { $env:SKILLOPT_OUT_ROOT } else { "outputs/mcqa_local_pilot" }
$Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

# 4a. Background GPU sampler -> $OutRoot/gpu.csv (5s interval)
$GpuLog = Join-Path $OutRoot "gpu.csv"
$SmiCmd = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$GpuJob = $null
if ($SmiCmd) {
    "timestamp,gpu_util_pct,mem_used_mib,mem_total_mib,temp_c,power_w" | Out-File -FilePath $GpuLog -Encoding ascii
    $GpuJob = Start-Job -ScriptBlock {
        param($logPath)
        while ($true) {
            $ts = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            $row = & nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null
            if ($row) { "$ts,$($row.Trim())" | Out-File -FilePath $logPath -Append -Encoding ascii }
            Start-Sleep -Seconds 5
        }
    } -ArgumentList $GpuLog
    Write-Host "[pilot] GPU sampler started (job $($GpuJob.Id)) -> $GpuLog"
} else {
    Write-Host "[pilot] nvidia-smi not found; skipping GPU sampler"
}

Write-Host "[pilot] optimizer=deepseek-chat  target=$Model  out_root=$OutRoot"
$Start = Get-Date
try {
    & $Py scripts/train.py --config configs/mcqa/local-pilot.yaml --out_root $OutRoot
} finally {
    if ($GpuJob) { Stop-Job -Job $GpuJob -ErrorAction SilentlyContinue; Remove-Job -Job $GpuJob -Force -ErrorAction SilentlyContinue }
}
$Elapsed = ((Get-Date) - $Start).TotalSeconds
Write-Host ("[pilot] done in {0:N1} s. Artifacts in $OutRoot (best_skill.md, history.json, skills/, gpu.csv)" -f $Elapsed)
