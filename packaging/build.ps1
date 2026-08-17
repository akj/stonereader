param(
    [switch] $Installer
)

$ErrorActionPreference = 'Stop'

function Invoke-Native {
    param(
        [Parameter(Mandatory)]
        [string] $Command,

        [Parameter(ValueFromRemainingArguments)]
        [string[]] $Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $version = & uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read the version from pyproject.toml (uv exited with code $LASTEXITCODE)."
    }
    $version = $version.Trim()
    Write-Host "StoneReader version: $version"

    if ($env:GITHUB_OUTPUT) {
        Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "version=$version" -Encoding utf8
    }

    Invoke-Native uv sync --locked --group build

    $sourceMetadata = Join-Path $repoRoot 'stonereader.egg-info'
    if (Test-Path -LiteralPath $sourceMetadata) {
        Remove-Item -LiteralPath $sourceMetadata -Recurse -Force
    }

    $distApp = Join-Path $repoRoot 'dist\StoneReader'
    if (Test-Path -LiteralPath $distApp) {
        Remove-Item -LiteralPath $distApp -Recurse -Force
    }

    Invoke-Native uv run pyinstaller packaging/stonereader.spec --noconfirm --distpath dist

    if ($Installer) {
        $isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
        if ($isccCommand) {
            $isccPath = $isccCommand.Source
        }
        else {
            $isccPath = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
            if (-not (Test-Path -LiteralPath $isccPath)) {
                throw 'Inno Setup Compiler (ISCC) was not found on PATH or in the default Inno Setup 6 install directory. Install Inno Setup 6 before building the installer.'
            }
        }

        Invoke-Native $isccPath packaging\installer.iss "/DAppVersion=$version"
    }
}
finally {
    Pop-Location
}
