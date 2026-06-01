#!/usr/bin/env pwsh
# Phase-04 SkillOpt training matrix for LogiQA (arm 3 = optimized skill from weak init).
# Each CONDITION is a config file with model.target baked in (the model is chosen by which
# config you run — never via env, so no .env clobber can pick the wrong target). Each
# condition runs x seeds via run_local_pilot.ps1, varying only the data split + loop seed.
# Idempotent: skips a run whose best_skill.md already exists (resume-aware).
# Default scope = gemma3:4b (the probe's sweet spot) x seeds 42/43/44; add another config
# entry (e.g. local-pilot-logiqa-qwen7b.yaml) to $conditions to extend.
$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Fail fast: the optimizer key must be present before spending GPU/seed time.
$EnvFile = Join-Path $ProjectRoot ".env.local-pilot"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $idx = $line.IndexOf("="); $k = $line.Substring(0,$idx).Trim(); $v = $line.Substring($idx+1).Trim()
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}
$key = $env:OPTIMIZER_OPENAI_API_KEY
if (-not $key -or $key -eq "sk-REPLACE_ME") {
  Write-Error "OPTIMIZER_OPENAI_API_KEY missing/placeholder in .env.local-pilot. Add the real DeepSeek key first."
  exit 1
}

# One entry per target condition; slug only labels the output dir (target lives in config).
$conditions = @(
  @{ config = "configs/mcqa/local-pilot-logiqa.yaml"; slug = "gemma3-4b" }
)
# seed -> per-seed split dir (seed 42 = the canonical split; 43/44 are re-partitions).
$seeds = @(
  @{ seed = 42; split = "data/mcqa_logiqa_split" },
  @{ seed = 43; split = "data/mcqa_logiqa_split_s43" },
  @{ seed = 44; split = "data/mcqa_logiqa_split_s44" }
)

# Target is config-driven; make sure no stale env tag is around to mislead anything.
Remove-Item Env:TARGET_DEPLOYMENT -ErrorAction SilentlyContinue

foreach ($c in $conditions) {
  foreach ($s in $seeds) {
    $out = "outputs/logiqa-train/$($c.slug)-s$($s.seed)"
    if (Test-Path "$out/best_skill.md") { Write-Host "[train] skip (done) $out"; continue }
    Write-Host "[train] === $($c.slug) (config $($c.config)) / seed $($s.seed) -> $out ==="
    $env:SKILLOPT_CONFIG    = $c.config
    $env:SKILLOPT_SPLIT_DIR = $s.split
    $env:SKILLOPT_SEED      = "$($s.seed)"
    $env:SKILLOPT_OUT_ROOT  = $out
    & "$PSScriptRoot/run_local_pilot.ps1"
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { Write-Host "[train] WARN run exited $LASTEXITCODE for $out" }
  }
}
Write-Host "[train] LOGIQA TRAIN MATRIX DONE"
