param(
    [Parameter(Mandatory = $true)]
    [string] $GroupPath,
    [string] $OutDir
)

$PSNativeCommandUseErrorActionPreference = $true
$ErrorActionPreference = "Stop"

if (!(Test-Path $GroupPath)) {
    Write-Error "Group file not found: $GroupPath"
    exit 1
}

$groupName = [System.IO.Path]::GetFileName($GroupPath)

$parts = ($Env:LC_GROUPS | ConvertFrom-Json -AsHashtable)[$groupName]["parts"]
$tempDir = [System.IO.Directory]::CreateTempSubdirectory()

$updatePath = $groupName + ".c4u"

if ($OutDir) {
    $updatePath = Join-Path $OutDir $updatePath
}

$updatePath = [System.IO.Path]::GetFullPath($updatePath, $PWD)
$GroupPath = Resolve-Path -Path $GroupPath

Remove-Item $updatePath -ErrorAction SilentlyContinue

$c4group = Resolve-Path -Path $Env:C4GROUP

# Download bases in order: the current repository (where fork-cut release
# parts such as v366 live) first, then the upstream (historical v360-v365 parts).
$bases = @()
if ($Env:GITHUB_SERVER_URL -and $Env:GITHUB_REPOSITORY) {
    $bases += "$($Env:GITHUB_SERVER_URL)/$($Env:GITHUB_REPOSITORY)"
}
$bases += "https://github.com/legacyclonk/LegacyClonk"

foreach ($part in $parts) {
    Write-Output "Downloading $part..."
    $outFile = Join-Path $tempDir.FullName $groupName
    $downloaded = $false

    foreach ($base in $bases) {
        $uri = "$base/releases/download/$part/$groupName"
        try {
            Invoke-WebRequest -Uri $uri -OutFile $outFile
            $downloaded = $true
            break
        }
        catch {
            Write-Output "Failed to download from $uri : $($_.Exception.Message)"
        }
    }

    if (!$downloaded) {
        Write-Error "Failed to download part '$part' from any source. Update aborted."
        exit 1
    }

    Write-Output "Adding support for $part..."

    Push-Location -Path $tempDir.FullName

    try {
        & $c4group "$updatePath" -g "$groupName" "$GroupPath" $Env:OBJVERSION
    }
    finally {
        Pop-Location
    }
}

