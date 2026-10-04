param(
    [string] $OutDir
)

$PSNativeCommandUseErrorActionPreference = $true
$ErrorActionPreference = "Stop"

$groups = ($Env:LC_GROUPS | ConvertFrom-Json -AsHashtable)["content"]

$parts = $groups["parts"]
$tempDir = [System.IO.Directory]::CreateTempSubdirectory()

$downloadedParts = [System.Collections.Generic.List[object]]::new()

foreach ($part in $parts) {
    Write-Output "Downloading $part..."
    $job = Start-ThreadJob -ScriptBlock {
        $partName = Split-Path -Path $using:part -Leaf
        $partPath = Join-Path $using:tempDir $partName
        Invoke-WebRequest -Uri "$using:part" -OutFile $partPath
        @{ PartPath = $partPath; Part = $partName }
    }

    $downloadedParts.Add($job)
}

# Release staging root: every shipped pack is copied here WITHOUT its
# Tests.c4f folders before packing (spec content-cleanup 4.2 -- test
# scenarios must never ship inside a packed group).
$stagingRoot = Join-Path $tempDir "release-staging"
New-Item -Path $stagingRoot -ItemType Directory | Out-Null

$groupPaths = [System.Collections.Generic.List[object]]::new()

foreach ($group in $groups.GetEnumerator() | Where-Object { $_.Name -like "*.c4?" }) {
    Write-Host "Packing $($group.Name)..."

    $sourceDir = Join-Path (Get-Location) $group.Name
    $stagedDir = Join-Path $stagingRoot $group.Name

    # Stage a release copy excluding every Tests.c4f folder. Copy-then-
    # prune works on the Windows runner and local pwsh fixtures alike.
    Copy-Item -Path $sourceDir -Destination $stagingRoot -Recurse
    Get-ChildItem -LiteralPath $stagedDir -Recurse -Directory -Filter "Tests.c4f" |
        Remove-Item -Recurse -Force

    & $Env:C4GROUP $stagedDir -p

    # Post-pack assertion (spec content-cleanup 6.1, NoShippedTests): the
    # packed group must not contain a Tests.c4f member.
    $memberListing = @(& $Env:C4GROUP $stagedDir -l)
    if (($memberListing -join "`n") -match "Tests\.c4f") {
        throw "NoShippedTests: packed group $($group.Name) contains a Tests.c4f member"
    }

    if ($OutDir) {
        Move-Item -Path $stagedDir -Destination $OutDir
        $groupPaths.Add((Resolve-Path -Path (Join-Path $OutDir $group.Name)))
    }
    else {
        $groupPaths.Add((Resolve-Path -Path $stagedDir))
    }
}

$partsDir = Join-Path $tempDir 'parts'
New-Item -Path $partsDir -ItemType Directory | Out-Null

# Empty parts lists (local fixture runs) would hand $null to Wait-Job's
# -Id parameter validation; guard so the pack loop stays testable.
if ($downloadedParts.Count -gt 0) {
    Wait-Job $downloadedParts | Out-Null
}

$c4group = Resolve-Path -Path $Env:C4GROUP

foreach ($partJob in $downloadedParts) {
    $partData = Receive-Job $partJob

    Remove-Item (Join-Path $partsDir "*")
    [System.IO.Compression.ZipFile]::ExtractToDirectory($partData.PartPath, $partsDir)

    Write-Output "`nAdding support for $($partData.Part)..."

    foreach ($groupPath in $groupPaths) {
        $groupName = Split-Path -Path $groupPath -Leaf
        $partPath = Join-Path $partsDir $groupName

        if (!(Test-Path $partPath)) {
            Write-Host "Part for $groupName not found, skipping"
            continue
        }

        Write-Output "$groupName..."

        $updatePath = $groupPath.Path + ".c4u"
        $allowMissingTarget = $groups[$groupName].'allow-missing-target'
        $updateOption = $allowMissingTarget ? '-ga' : '-g'

        Push-Location -Path $partsDir

        try {
            & $c4group "$updatePath" $updateOption "$groupName" "$groupPath" $Env:OBJVERSION
        }
        finally {
            Pop-Location
        }
    }
}

$combinedGroup = "lc_$Env:OBJVERSIONNODOTS.c4u"

if ($OutDir) {
    $combinedGroup = Join-Path $OutDir $combinedGroup
}

New-Item -Path $combinedGroup -ItemType Directory | Out-Null

foreach ($groupPath in $groupPaths) {
    $updateFile = "$($groupPath.Path).c4u"
    if (Test-Path -LiteralPath $updateFile) {
        Copy-Item -Path $updateFile -Destination $combinedGroup
    } else {
        Write-Output "No update group for $(Split-Path -Leaf $groupPath) (absent from all parts); skipping"
    }
}

& $Env:C4GROUP "$combinedGroup" -p
