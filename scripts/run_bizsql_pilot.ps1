#!/usr/bin/env pwsh
# Launch the bizsql local pilot: DeepSeek optimizer (cloud) + local Qwen2.5-7B target (Ollama).
# Resume-aware: re-running continues the same outputs/bizsql_local_pilot run.
# Same structure as run_mbpp_pilot.ps1; pre-flight ensures business.sqlite exists
# and runs one gold SQL through the evaluator (no GPU).
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 1. Load .env.local-pilot if present (secrets + temp pinning only).
$OrchKeys = @("SKILLOPT_CONFIG", "SKILLOPT_SPLIT_DIR", "SKILLOPT_SEED", "SKILLOPT_OUT_ROOT")
$CallerOrch = @{}
foreach ($k in $OrchKeys) {
    $v = [Environment]::GetEnvironmentVariable($k)
    if ($v) { $CallerOrch[$k] = $v }
}
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
    foreach ($k in $CallerOrch.Keys) { Set-Item -Path "Env:$k" -Value $CallerOrch[$k] }
    Write-Host "[pilot] loaded $EnvFile (preserved caller orchestration: $($CallerOrch.Keys -join ', '))"
} else {
    Write-Host "[pilot] no .env.local-pilot found; relying on current environment"
}

# 2. Fail fast if no optimizer key is present.
if (-not $env:OPTIMIZER_OPENAI_API_KEY -and -not $env:OPTIMIZER_CLAUDE_API_KEY) {
    Write-Error "No optimizer key set. Need OPTIMIZER_OPENAI_API_KEY (DeepSeek) or OPTIMIZER_CLAUDE_API_KEY (Sonnet) in .env.local-pilot."
    exit 1
}

# 3. Resolve config + interpreter, then derive the target from the CONFIG itself.
$env:PYTHONUTF8 = "1"   # guards config loading on non-UTF8 consoles
$Config  = if ($env:SKILLOPT_CONFIG)   { $env:SKILLOPT_CONFIG }   else { "configs/bizsql/local-pilot.yaml" }
$OutRoot = if ($env:SKILLOPT_OUT_ROOT) { $env:SKILLOPT_OUT_ROOT } else { "outputs/bizsql_local_pilot" }
$Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Model = (& $Py -c "import sys; sys.path.insert(0,'.'); from skillopt.config import load_config, flatten_config, is_structured; c=load_config(sys.argv[1]); f=flatten_config(c) if is_structured(c) else c; print((f.get('target_model') or '').strip())" $Config).Trim()
if (-not $Model) { Write-Error "Could not resolve model.target from $Config"; exit 1 }
$Optim = (& $Py -c "import sys; sys.path.insert(0,'.'); from skillopt.config import load_config, flatten_config, is_structured; c=load_config(sys.argv[1]); f=flatten_config(c) if is_structured(c) else c; print((f.get('optimizer_model') or '').strip())" $Config).Trim()

# 3a. Ensure the seeded DB exists (regenerate if missing).
$DbPath = Join-Path $ProjectRoot "data/bizsql/business.sqlite"
if (-not (Test-Path $DbPath)) {
    Write-Host "[pilot] business.sqlite missing; seeding ..."
    & $Py scripts/seed_bizsql_db.py
}

# 3b. SQL smoke: run one gold SQL from the split through the evaluator (no GPU).
$SplitDir = if ($env:SKILLOPT_SPLIT_DIR) { $env:SKILLOPT_SPLIT_DIR } else { "data/bizsql_split_s42" }
$SqlOk = (& $Py -c "import sys,json,os; sys.path.insert(0,'.'); from skillopt.envs.bizsql.evaluator import run_sql, canonicalize; p=os.path.join(sys.argv[1],'train','items.json'); it=json.load(open(p,encoding='utf-8'))[0]; ok,rows,_=run_sql(it['gold_sql'], it['db_path']); print('OK' if ok and canonicalize(rows)==canonicalize(it['gold_result']) else 'FAIL')" $SplitDir).Trim()
if ($SqlOk -ne "OK") { Write-Error "SQL smoke failed (gold SQL did not reproduce gold_result) for split $SplitDir"; exit 1 }
Write-Host "[pilot] SQL smoke OK (gold SQL reproduces gold_result) on $SplitDir"

# 4. Ensure Ollama is up and the target (from the config) is pulled + warm
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

Write-Host "[pilot] optimizer=$Optim  target=$Model  config=$Config  out_root=$OutRoot"
$Start = Get-Date
try {
    $trainArgs = @("scripts/train.py", "--config", $Config, "--out_root", $OutRoot)
    if ($env:SKILLOPT_SPLIT_DIR) { $trainArgs += @("--split_dir", $env:SKILLOPT_SPLIT_DIR) }
    if ($env:SKILLOPT_SEED)      { $trainArgs += @("--seed", $env:SKILLOPT_SEED) }
    & $Py @trainArgs
} finally {
    if ($GpuJob) { Stop-Job -Job $GpuJob -ErrorAction SilentlyContinue; Remove-Job -Job $GpuJob -Force -ErrorAction SilentlyContinue }
}
$Elapsed = ((Get-Date) - $Start).TotalSeconds
Write-Host ("[pilot] done in {0:N1} s. Artifacts in $OutRoot (best_skill.md, history.json, skills/, gpu.csv)" -f $Elapsed)
