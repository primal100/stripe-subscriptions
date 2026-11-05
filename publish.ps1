<#
.SYNOPSIS
Build, validate, and upload the package to PyPI or TestPyPI.
.EXAMPLE
./publish.ps1 -BuildOnly
.EXAMPLE
./publish.ps1 -Repository testpypi
#>
[CmdletBinding()]
param(
    [ValidateSet('pypi', 'testpypi')]
    [string]$Repository = 'pypi',
    [string]$Python = 'python',
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-ReleasePython {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed (exit $LASTEXITCODE); publishing stopped."
    }
}

Push-Location $PSScriptRoot
try {
    # Install these in the selected interpreter first: python -m pip install build twine
    Invoke-ReleasePython -Arguments @('-c', 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"; import build, twine')

    $releaseDirectory = Join-Path $PSScriptRoot ('dist/release-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
    Invoke-ReleasePython -Arguments @('-m', 'build', '--outdir', $releaseDirectory)

    $wheels = @(Get-ChildItem -LiteralPath $releaseDirectory -File -Filter '*.whl')
    $archives = @(Get-ChildItem -LiteralPath $releaseDirectory -File -Filter '*.tar.gz')
    if ($wheels.Count -ne 1 -or $archives.Count -ne 1) {
        throw 'Expected exactly one wheel and one source distribution; publishing stopped.'
    }
    $artifacts = @($wheels[0].FullName, $archives[0].FullName)
    Invoke-ReleasePython -Arguments (@('-m', 'twine', 'check', '--strict') + $artifacts)

    Write-Host "Validated distributions: $releaseDirectory"
    if ($BuildOnly) {
        Write-Host 'Build-only mode: nothing uploaded.'
    } else {
        Write-Host "Uploading to $Repository. Enter that repository's API token if prompted."
        Invoke-ReleasePython -Arguments (@('-m', 'twine', 'upload', '--repository', $Repository, '--username', '__token__') + $artifacts)
    }
} finally {
    Pop-Location
}
