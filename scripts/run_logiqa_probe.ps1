#!/usr/bin/env pwsh
# Headroom-probe gate: raw + generic-CoT baselines (eval-only, no optimizer) for
# each LogiQA target. Target is passed explicitly via --target (the eval's .env
# loader forces file>shell, so a bare $env:TARGET_DEPLOYMENT would be clobbered by
# any TARGET_DEPLOYMENT line in .env.local-pilot). Idempotent: skips a run whose
# summary.json already exists. summary.json records the resolved target for audit.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONUTF8 = "1"
$py = ".venv\Scripts\python.exe"
$splitDir = "data/mcqa_logiqa_split"   # seed-42 test (200 items)

$targets = @(
  @{ tag = "qwen2.5:1.5b";                slug = "qwen25-1.5b" },
  @{ tag = "llama3.2:latest";             slug = "llama32-3b" },
  @{ tag = "gemma3:4b";                   slug = "gemma3-4b" },
  @{ tag = "qwen2.5:7b-instruct-q4_K_M";  slug = "qwen25-7b" }
)
$arms = @(
  @{ skill = "skillopt/envs/mcqa/skills/initial-weak.md"; name = "raw" },
  @{ skill = "skillopt/envs/mcqa/skills/generic-cot.md";  name = "cot" }
)

foreach ($t in $targets) {
  foreach ($a in $arms) {
    $out = "outputs/logiqa-probe/$($t.slug)-$($a.name)"
    if (Test-Path "$out/summary.json") { Write-Host "[probe] skip (done) $out"; continue }
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    Write-Host "[probe] === $($t.tag) / $($a.name) ==="
    & $py scripts/eval_skill_on_dataset.py --skill $a.skill --split-dir $splitDir --split test --out-dir $out --workers 8 --target $t.tag 2>&1 |
      Tee-Object -FilePath "$out/run.log" | Select-Object -Last 3
  }
}
Write-Host "[probe] PROBE DONE"
