#!/usr/bin/env pwsh
# Optimizer-comparison pilot: does the OPTIMIZER model change SkillOpt results?
# 6 runs = 3 datasets (CSQA, SocialIQA, LogiQA) x 2 optimizers, seed 42 only.
#   DeepSeek arm -> deepseek-v4-pro     (direct DeepSeek API, key OPTIMIZER_OPENAI_API_KEY)
#   Sonnet   arm -> claude-sonnet-4-6   (direct Anthropic API, key OPTIMIZER_CLAUDE_API_KEY)
# Target stays local (config-driven: qwen2.5:7b for CSQA/SIQA, gemma3:4b for LogiQA).
# Output dirs are namespaced by optimizer so nothing clobbers prior runs.
# Idempotent: skips a run whose best_skill.md already exists. After this pilot, decide
# whether to scale to the full 3-seed matrix (see the run guide in plans/).
$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Load .env.local-pilot into the process env (so both optimizer keys are available).
$EnvFile = Join-Path $ProjectRoot ".env.local-pilot"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $idx = $line.IndexOf("="); $k = $line.Substring(0, $idx).Trim(); $v = $line.Substring($idx + 1).Trim()
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}
if (-not $env:OPTIMIZER_OPENAI_API_KEY) { Write-Error "OPTIMIZER_OPENAI_API_KEY (DeepSeek) missing in .env.local-pilot."; exit 1 }
if (-not $env:OPTIMIZER_CLAUDE_API_KEY) { Write-Error "OPTIMIZER_CLAUDE_API_KEY (Anthropic) missing in .env.local-pilot."; exit 1 }

$env:PYTHONUTF8 = "1"
$Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

# Fail-fast: ping both optimizer endpoints (1 token each) before spending GPU time.
Write-Host "[pilot] smoke-testing optimizer endpoints (DeepSeek + Anthropic)..."
& $Py -u -c @"
import os, sys, time
from openai import OpenAI
checks = [
    ('deepseek-v4-pro',    'https://api.deepseek.com/v1',     os.environ['OPTIMIZER_OPENAI_API_KEY']),
    ('claude-sonnet-4-6',  'https://api.anthropic.com/v1',    os.environ['OPTIMIZER_CLAUDE_API_KEY']),
]
for model, base, key in checks:
    last = None
    for attempt in range(3):  # tolerate a transient 4xx before aborting
        try:
            OpenAI(api_key=key, base_url=base).chat.completions.create(
                model=model, messages=[{'role':'user','content':'ok'}], max_tokens=5)
            print(f'  OK   {model} @ {base}', flush=True); last = None; break
        except Exception as e:
            last = e; time.sleep(2)
    if last is not None:
        print(f'  FAIL {model} @ {base}: {last}', flush=True); sys.exit(1)
"@
if ($LASTEXITCODE -ne 0) { Write-Error "[pilot] optimizer smoke test failed; aborting before GPU spend."; exit 1 }

# 6 conditions: dataset x optimizer. split_dir passed explicitly; target lives in config.
$conditions = @(
  @{ ds = "csqa";   opt = "deepseek-v4-pro";  config = "configs/mcqa/local-pilot.yaml";               split = "data/mcqa_csqa_split_v2"; tslug = "qwen7b" },
  @{ ds = "csqa";   opt = "sonnet-4-6";       config = "configs/mcqa/local-pilot-sonnet.yaml";        split = "data/mcqa_csqa_split_v2"; tslug = "qwen7b" },
  @{ ds = "siqa";   opt = "deepseek-v4-pro";  config = "configs/mcqa/local-pilot-siqa.yaml";          split = "data/mcqa_siqa_split";    tslug = "qwen7b" },
  @{ ds = "siqa";   opt = "sonnet-4-6";       config = "configs/mcqa/local-pilot-siqa-sonnet.yaml";   split = "data/mcqa_siqa_split";    tslug = "qwen7b" },
  @{ ds = "logiqa"; opt = "deepseek-v4-pro";  config = "configs/mcqa/local-pilot-logiqa.yaml";         split = "data/mcqa_logiqa_split";  tslug = "gemma3-4b" },
  @{ ds = "logiqa"; opt = "sonnet-4-6";       config = "configs/mcqa/local-pilot-logiqa-sonnet.yaml";  split = "data/mcqa_logiqa_split";  tslug = "gemma3-4b" }
)
$seed = 42

# Target is config-driven; clear any stale env tag so it can't override the config.
Remove-Item Env:TARGET_DEPLOYMENT -ErrorAction SilentlyContinue

foreach ($c in $conditions) {
  $out = "outputs/$($c.ds)-train/$($c.opt)/$($c.tslug)-s$seed"
  if (Test-Path "$out/best_skill.md") { Write-Host "[pilot] skip (done) $out"; continue }
  Write-Host "[pilot] === $($c.ds) / opt=$($c.opt) / seed $seed -> $out ==="
  $env:SKILLOPT_CONFIG    = $c.config
  $env:SKILLOPT_SPLIT_DIR = $c.split
  $env:SKILLOPT_SEED      = "$seed"
  $env:SKILLOPT_OUT_ROOT  = $out
  & "$PSScriptRoot/run_local_pilot.ps1"
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { Write-Host "[pilot] WARN run exited $LASTEXITCODE for $out" }
}
Write-Host "[pilot] OPTIMIZER PILOT DONE (6 runs, seed $seed)"
