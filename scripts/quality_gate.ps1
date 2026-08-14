[CmdletBinding()]
param(
    [ValidateSet("core", "full", "unused")]
    [string]$Mode = "core"
)

$ErrorActionPreference = "Stop"
$uv = if ($env:UV_BIN) { $env:UV_BIN } else { "uv" }
$uvx = if ($env:UVX_BIN) { $env:UVX_BIN } else { "uvx" }

function Invoke-QualityCommand {
    param([string]$Label, [string]$Executable, [string[]]$Arguments)

    Write-Host "[quality][$Mode] $Label"
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Quality command failed: $Label"
    }
}

switch ($Mode) {
    "core" {
        Invoke-QualityCommand "repository development rules" $uv @("run", "--extra", "dev", "python", "scripts/repository_guard.py", "--check")
        Invoke-QualityCommand "ruff check (core scope)" $uv @("run", "--extra", "dev", "ruff", "check", "api", "agent/domain", "agent/tools", "agent/application/contracts.py")
        Invoke-QualityCommand "ty (core scope)" $uvx @("ty", "check", "api", "agent/domain", "agent/tools", "agent/application/contracts.py")
    }
    "full" {
        Invoke-QualityCommand "repository development rules" $uv @("run", "--extra", "dev", "python", "scripts/repository_guard.py", "--check")
        Invoke-QualityCommand "ruff check (full repo)" $uv @("run", "--extra", "dev", "ruff", "check", ".")
        Invoke-QualityCommand "ty (full agent package)" $uvx @("ty", "check", "api", "agent")
    }
    "unused" {
        Invoke-QualityCommand "unused imports and variables" $uv @("run", "--extra", "dev", "python", "scripts/python_cleanup.py", "check")
        Invoke-QualityCommand "suspected dead code report" $uv @("run", "--extra", "dev", "python", "scripts/python_cleanup.py", "deadcode")
    }
}
