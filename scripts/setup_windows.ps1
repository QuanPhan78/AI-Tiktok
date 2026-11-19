<# Install Content Studio without replacing existing settings or data. #>
[CmdletBinding()]
param([switch]$WithTests)

$ErrorActionPreference = 'Stop'
$repoPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'

function Assert-Python([string]$Executable, [string[]]$Prefix = @()) {
    & $Executable @Prefix -c 'import sys; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info >= (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required. Python 3.12/3.13 are checked in GitHub Actions.' }
}

Push-Location -LiteralPath $repoPath
try {
    if (Test-Path -LiteralPath (Join-Path $repoPath '.venv')) {
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw 'The existing .venv is incomplete or belongs to another OS. Keep it safe and resolve it before retrying; nothing was replaced.'
        }
        Assert-Python $pythonPath
        Write-Host 'Keeping the existing Python environment.'
    } else {
        $candidate = $null
        $prefix = @()
        if (Get-Command py -ErrorAction SilentlyContinue) {
            foreach ($version in @('-3.13', '-3.12', '-3')) {
                try {
                    & py $version -c 'import sys; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info >= (3, 12) else 1)' 2>$null
                } catch { continue }
                if ($LASTEXITCODE -eq 0) { $candidate = 'py'; $prefix = @($version); break }
            }
        }
        if (-not $candidate -and (Get-Command python -ErrorAction SilentlyContinue)) {
            Assert-Python 'python'
            $candidate = 'python'
        }
        if (-not $candidate) { throw 'Install Python 3.12/3.13 with the Python launcher, reopen PowerShell, then retry.' }
        & $candidate @prefix -m venv (Join-Path $repoPath '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Check Python installation and free disk space.' }
    }

    $requirementsPath = Join-Path $repoPath 'requirements.txt'
    if ($WithTests) {
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 20 or newer for -WithTests, reopen PowerShell, then retry.' }
        & node -e 'process.exit(Number(process.versions.node.split(/[.]/)[0]) >= 20 ? 0 : 1)'
        if ($LASTEXITCODE -ne 0) { throw 'Node.js 20 or newer is required for -WithTests.' }
        $requirementsPath = Join-Path $repoPath 'requirements-test.txt'
    }
    & $pythonPath -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) { throw 'Library installation failed. Check the network and retry; existing settings were kept.' }

    foreach ($relative in @('.env', 'integrations\long-v2\.env')) {
        $targetPath = Join-Path $repoPath $relative
        if (Test-Path -LiteralPath $targetPath) {
            Write-Host "Kept existing settings: $relative"
        } else {
            $bytes = [System.IO.File]::ReadAllBytes("$targetPath.example")
            # CreateNew also refuses to overwrite a file created concurrently.
            $stream = [System.IO.File]::Open($targetPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
            try {
                $stream.Write($bytes, 0, $bytes.Length)
            } finally { $stream.Dispose() }
            Write-Host "Created settings template: $relative"
        }
    }
    Write-Host 'Installation finished. Fill in your local settings using docs/SETUP_WINDOWS.md.'
    Write-Host 'Check: .\.venv\Scripts\python.exe scripts/check_setup.py --profile studio'
    Write-Host 'Start the full system: .\.venv\Scripts\python.exe scripts/start_personal.py'
    Write-Host 'This installer did not start services, connect accounts, or enable publishing.'
} finally { Pop-Location }
