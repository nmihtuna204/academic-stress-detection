# Build main.pdf locally with MiKTeX (pdfLaTeX + BibTeX).
# Usage (PowerShell, from this folder):   .\build.ps1
# Missing LaTeX packages are installed automatically on first use.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# MiKTeX walks every PATH entry and aborts on entries that are files rather than
# directories (this machine has a .jar and an .exe listed in PATH). Use a cleaned
# PATH for this script only, with the scoop MiKTeX binaries first.
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) } | Select-Object -Unique) -join ';'
$miktexBin = "$env:USERPROFILE\scoop\apps\latex\current\texmfs\install\miktex\bin\x64"
if (Test-Path $miktexBin) { $env:PATH = "$miktexBin;$env:PATH" }

$pdflatex = @("-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "main.tex")

Write-Host "[1/4] pdflatex (first pass)"
pdflatex @pdflatex | Out-Null
Write-Host "[2/4] bibtex"
bibtex main | Out-Null
Write-Host "[3/4] pdflatex (resolve citations)"
pdflatex @pdflatex | Out-Null
Write-Host "[4/4] pdflatex (resolve references)"
pdflatex @pdflatex | Out-Null

$errors = Select-String -Path main.log -Pattern "^! |^.*:\d+: " -ErrorAction SilentlyContinue
if ($errors) {
    Write-Host "Errors found in main.log:" -ForegroundColor Red
    $errors | ForEach-Object { $_.Line }
    exit 1
}
$pages = (Select-String -Path main.log -Pattern "Output written on main.pdf \((\d+) pages").Matches.Groups[1].Value
Write-Host "Done: main.pdf ($pages pages)" -ForegroundColor Green
