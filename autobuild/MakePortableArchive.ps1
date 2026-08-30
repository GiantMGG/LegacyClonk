param(
    [Parameter(Mandatory = $true)]
    [string] $Version,

    [Parameter(Mandatory = $true)]
    [string] $PlatformSuffix,

    [Parameter(Mandatory = $true)]
    [ValidateSet('portable', 'full')]
    [string] $Kind,

    [Parameter(Mandatory = $true)]
    [string] $SourceDir,

    [Parameter(Mandatory = $true)]
    [string] $OutDir,

    [string] $Commit = '',

    [string] $Tag = '',

    [string] $BuiltUtc = '',

    [string] $DepsLock = 'deps.lock'
)

$PSNativeCommandUseErrorActionPreference = $true
$ErrorActionPreference = 'Stop'

if (-not $BuiltUtc) {
    $BuiltUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
}

# --- 1. Validate inputs -----------------------------------------------------

if (-not (Test-Path $SourceDir)) {
    throw "SourceDir not found: $SourceDir"
}
if (-not (Get-ChildItem -Path $SourceDir -Filter 'clonk*' -ErrorAction SilentlyContinue)) {
    throw "SourceDir contains no clonk* entry: $SourceDir"
}
if (-not (Test-Path $DepsLock)) {
    throw "deps.lock not found: $DepsLock"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# --- 2. Parse deps.lock (minimal section-aware reader) ----------------------

function Get-DepsLockSections {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string[]] $Sections
    )

    $wanted = [ordered]@{}
    foreach ($section in $Sections) {
        $wanted[$section] = [System.Collections.Generic.List[string]]::new()
    }

    $current = ''
    foreach ($line in Get-Content -Path $Path) {
        if ($line -match '^\s*\[(.+?)\]\s*$') {
            $current = $Matches[1]
        }
        elseif ($current -and $wanted.Contains($current) -and $line -match '^\s*([A-Za-z0-9_.\-]+)\s*=\s*(\S.*)$') {
            $wanted[$current].Add("$($Matches[1]) = $($Matches[2])")
        }
    }
    return $wanted
}

$lockSections = Get-DepsLockSections -Path $DepsLock -Sections @('meta', 'tools', 'tarballs', 'spdlog')

# --- 3. Write BUILD_INFO.txt ------------------------------------------------

$buildInfoLines = [System.Collections.Generic.List[string]]::new()
$buildInfoLines.Add('LegacyClonk portable archive — build provenance')
$buildInfoLines.Add('=================================================')
$buildInfoLines.Add('Product:        LegacyClonk')
$buildInfoLines.Add("Version:        $Version")
$buildInfoLines.Add("Platform:       $PlatformSuffix")
$buildInfoLines.Add("Archive kind:   $Kind")
$buildInfoLines.Add("Commit:         $Commit")
$buildInfoLines.Add("Tag:            $Tag")
$buildInfoLines.Add("Built (UTC):    $BuiltUtc")
$buildInfoLines.Add('')
$buildInfoLines.Add('deps.lock:')
foreach ($section in @('meta', 'tools', 'tarballs', 'spdlog')) {
    $buildInfoLines.Add("[$section]")
    foreach ($entry in $lockSections[$section]) {
        $buildInfoLines.Add("    $entry")
    }
}
$buildInfoLines.Add('')
$buildInfoLines.Add('Verify this download against the release-page SHA256SUMS:')
$buildInfoLines.Add('    sha256sum -c SHA256SUMS')

$buildInfoPath = Join-Path $SourceDir 'BUILD_INFO.txt'
$buildInfoLines | Set-Content -Path $buildInfoPath

# --- 4. Pack ----------------------------------------------------------------

$name = "LegacyClonk-$Version-$PlatformSuffix-$Kind.tar.gz"
$archive = Join-Path $OutDir $name
tar -czf $archive -C $SourceDir .

# --- 5. Checksum ------------------------------------------------------------

$hash = (Get-FileHash -Algorithm SHA256 -Path $archive).Hash.ToLowerInvariant()
$sumLine = "$hash  $name"
Set-Content -Path (Join-Path $OutDir "$name.sha256") -Value $sumLine
Add-Content -Path (Join-Path $OutDir 'SHA256SUMS.part') -Value $sumLine

# --- 6. Report --------------------------------------------------------------

Write-Host "Archive: $archive"
Write-Host "SHA-256: $hash"
