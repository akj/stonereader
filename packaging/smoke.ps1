param(
    [Parameter(Mandatory)]
    [string] $ExePath
)

$ErrorActionPreference = 'Stop'

try {
    if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
        [Console]::Error.WriteLine("Smoke test failed: executable not found at '$ExePath'.")
        exit 1
    }

    $process = Start-Process $ExePath -PassThru
    $id = $process.Id

    Start-Sleep -Seconds 10

    $runningProcess = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($null -eq $runningProcess -or $runningProcess.HasExited) {
        [Console]::Error.WriteLine("Smoke test failed: process $id likely crashed within the 10-second wait window (for example, due to an import or DLL failure).")
        exit 1
    }

    Stop-Process -Id $id -Force
    Write-Host "Smoke test passed: process $id remained running for 10 seconds."
    exit 0
}
catch {
    [Console]::Error.WriteLine("Smoke test failed unexpectedly: $($_.Exception.Message)")
    exit 1
}
