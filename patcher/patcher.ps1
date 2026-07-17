param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [switch]$AutoInstall,
    [string]$GamePath,
    [ValidateSet("Menu", "Install", "Status", "Restore")]
    [string]$Action = "Menu",
    [switch]$Yes
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

$Creator = "madamnut"
$RepositoryUrl = "https://github.com/madamnut/elder-scrolls-arena-korean"
$LatestReleaseApi = "https://api.github.com/repos/madamnut/elder-scrolls-arena-korean/releases/latest"
$SteamAppId = "1812290"
$StateDirectoryName = ".arena-korean-patch"
$ManifestPath = Join-Path $PackageRoot "patcher\manifest.json"

function Write-Header {
    param([string]$Version)
    Clear-Host
    Write-Host "=================================================="
    Write-Host " 엘더스크롤 아레나 한글 패치 $Version"
    Write-Host " 제작: $Creator"
    Write-Host " GitHub: $RepositoryUrl"
    Write-Host "=================================================="
    Write-Host ""
}

function Write-ProgressBar {
    param(
        [ValidateRange(0, 100)][int]$Percent,
        [string]$Message,
        [switch]$Complete
    )
    $width = 20
    $filled = [Math]::Floor($Percent * $width / 100)
    $empty = $width - $filled
    $bar = ("#" * $filled) + ("-" * $empty)
    $line = "`r[{0}] {1,3}%  {2}" -f $bar, $Percent, $Message
    Write-Host $line.PadRight(78) -NoNewline
    if ($Complete -or $Percent -eq 100) {
        Write-Host ""
    }
}

function Write-Ok {
    param([string]$Message)
    Write-Host ("[완료] " + $Message) -ForegroundColor Green
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Resolve-SafeChildPath {
    param(
        [string]$Root,
        [string]$RelativePath
    )
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $relative = $RelativePath.Replace('/', '\').TrimStart('\')
    $full = [IO.Path]::GetFullPath((Join-Path $rootFull $relative))
    if (-not $full.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "안전하지 않은 상대 경로입니다: $RelativePath"
    }
    return $full
}

function Test-ArenaRoot {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try { $full = [IO.Path]::GetFullPath($Path) } catch { return $false }
    $required = @(
        "ARENA\ACD.EXE",
        "ARENA\GLOBAL.BSA",
        "DOSBox-0.74\arena.conf",
        "Arena (Full Screen).bat",
        "Arena (Windowed).bat"
    )
    foreach ($relative in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $full $relative) -PathType Leaf)) {
            return $false
        }
    }
    return $true
}

function Get-SteamRoots {
    $roots = New-Object 'System.Collections.Generic.List[string]'
    $registryPaths = @(
        "HKCU:\Software\Valve\Steam",
        "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam",
        "HKLM:\SOFTWARE\Valve\Steam"
    )
    foreach ($registryPath in $registryPaths) {
        try {
            $item = Get-ItemProperty -LiteralPath $registryPath
            foreach ($property in @("SteamPath", "InstallPath")) {
                if ($item.PSObject.Properties.Name -contains $property) {
                    $value = [string]$item.$property
                    if (-not [string]::IsNullOrWhiteSpace($value) -and (Test-Path -LiteralPath $value)) {
                        $roots.Add([IO.Path]::GetFullPath($value))
                    }
                }
            }
        } catch { }
    }
    if (${env:ProgramFiles(x86)}) {
        $default = Join-Path ${env:ProgramFiles(x86)} "Steam"
        if (Test-Path -LiteralPath $default) { $roots.Add([IO.Path]::GetFullPath($default)) }
    }
    return $roots | Select-Object -Unique
}

function Get-ArenaCandidates {
    $libraries = New-Object 'System.Collections.Generic.List[string]'
    foreach ($steamRoot in Get-SteamRoots) {
        $libraries.Add($steamRoot)
        $libraryFile = Join-Path $steamRoot "steamapps\libraryfolders.vdf"
        if (-not (Test-Path -LiteralPath $libraryFile)) { continue }
        $content = [IO.File]::ReadAllText($libraryFile)
        foreach ($match in [regex]::Matches($content, '"path"\s+"([^"]+)"')) {
            $path = $match.Groups[1].Value.Replace('\\', '\')
            if (Test-Path -LiteralPath $path) { $libraries.Add([IO.Path]::GetFullPath($path)) }
        }
    }

    $candidates = New-Object 'System.Collections.Generic.List[string]'
    foreach ($library in ($libraries | Select-Object -Unique)) {
        $manifest = Join-Path $library "steamapps\appmanifest_$SteamAppId.acf"
        if (-not (Test-Path -LiteralPath $manifest)) { continue }
        $content = [IO.File]::ReadAllText($manifest)
        $match = [regex]::Match($content, '"installdir"\s+"([^"]+)"')
        if (-not $match.Success) { continue }
        $candidate = Join-Path $library ("steamapps\common\" + $match.Groups[1].Value)
        if (Test-ArenaRoot $candidate) { $candidates.Add([IO.Path]::GetFullPath($candidate)) }
    }
    $seen = @{}
    $uniqueCandidates = New-Object 'System.Collections.Generic.List[string]'
    foreach ($candidate in $candidates) {
        $key = $candidate.ToLowerInvariant()
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $uniqueCandidates.Add($candidate)
        }
    }
    return $uniqueCandidates
}

function Select-ArenaRoot {
    param([string]$RequestedPath)
    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        if (-not (Test-ArenaRoot $RequestedPath)) {
            throw "지정한 경로에서 지원되는 Arena 설치를 찾지 못했습니다: $RequestedPath"
        }
        return [IO.Path]::GetFullPath($RequestedPath)
    }

    Write-ProgressBar 3 "Steam 설치 경로 탐색 중..."
    $candidates = @(Get-ArenaCandidates)
    if ($candidates.Count -eq 1) {
        Write-ProgressBar 8 "게임 경로 확인 완료" -Complete
        return $candidates[0]
    }
    if ($candidates.Count -gt 1) {
        Write-ProgressBar 8 "여러 설치 경로 발견" -Complete
        for ($index = 0; $index -lt $candidates.Count; $index++) {
            Write-Host ("[{0}] {1}" -f ($index + 1), $candidates[$index])
        }
        $selection = Read-Host "사용할 게임 경로 번호"
        $number = 0
        if ([int]::TryParse($selection, [ref]$number) -and $number -ge 1 -and $number -le $candidates.Count) {
            return $candidates[$number - 1]
        }
        throw "올바른 경로 번호를 선택하지 않았습니다."
    }

    Write-ProgressBar 8 "자동 탐색 실패" -Complete
    $manual = Read-Host "The Elder Scrolls Arena 설치 폴더의 전체 경로"
    $manual = $manual.Trim().Trim('"')
    if (-not (Test-ArenaRoot $manual)) {
        throw "입력한 경로에서 지원되는 Arena 설치를 찾지 못했습니다."
    }
    return [IO.Path]::GetFullPath($manual)
}

function Copy-StreamLength {
    param(
        [IO.Stream]$InputStream,
        [IO.Stream]$OutputStream,
        [long]$Length
    )
    $buffer = New-Object byte[] 1048576
    $remaining = $Length
    while ($remaining -gt 0) {
        $take = [int][Math]::Min($buffer.Length, $remaining)
        $read = $InputStream.Read($buffer, 0, $take)
        if ($read -le 0) { throw "델타 데이터를 읽는 중 예기치 않게 파일이 끝났습니다." }
        $OutputStream.Write($buffer, 0, $read)
        $remaining -= $read
    }
}

function Apply-ArenaDelta {
    param(
        [string]$SourcePath,
        [string]$DeltaPath,
        [string]$OutputPath
    )
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($DeltaPath)
    try {
        $manifestEntry = $archive.GetEntry("delta.json")
        if ($null -eq $manifestEntry) { throw "델타에 delta.json이 없습니다." }
        $reader = New-Object IO.StreamReader($manifestEntry.Open(), [Text.Encoding]::UTF8)
        try { $delta = ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
        if ($delta.format -ne "arena-korean-delta-v1") { throw "지원하지 않는 델타 형식입니다." }
        if ((Get-Item -LiteralPath $SourcePath).Length -ne [long]$delta.sourceSize -or
            (Get-Sha256 $SourcePath) -ne ([string]$delta.sourceSha256).ToUpperInvariant()) {
            throw "델타 원본 파일 해시가 일치하지 않습니다: $SourcePath"
        }

        $parent = Split-Path -Parent $OutputPath
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        $temporary = $OutputPath + ".new"
        $source = [IO.File]::Open($SourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        $output = [IO.File]::Open($temporary, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            foreach ($operation in $delta.operations) {
                if ($operation.type -eq "copy") {
                    $null = $source.Seek([long]$operation.sourceOffset, [IO.SeekOrigin]::Begin)
                    Copy-StreamLength $source $output ([long]$operation.length)
                } elseif ($operation.type -eq "data") {
                    $entry = $archive.GetEntry([string]$operation.file)
                    if ($null -eq $entry) { throw "델타 데이터가 없습니다: $($operation.file)" }
                    $stream = $entry.Open()
                    try { Copy-StreamLength $stream $output ([long]$operation.length) } finally { $stream.Dispose() }
                } else {
                    throw "알 수 없는 델타 명령입니다: $($operation.type)"
                }
            }
        } finally {
            $output.Dispose()
            $source.Dispose()
        }
        if ((Get-Item -LiteralPath $temporary).Length -ne [long]$delta.targetSize -or
            (Get-Sha256 $temporary) -ne ([string]$delta.targetSha256).ToUpperInvariant()) {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
            throw "델타 결과 검증에 실패했습니다: $OutputPath"
        }
        Move-Item -LiteralPath $temporary -Destination $OutputPath -Force
    } finally {
        $archive.Dispose()
    }
}

function Copy-ArenaDirectory {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$StartPercent,
        [int]$EndPercent
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $files = @(Get-ChildItem -LiteralPath $Source -Recurse -File -Force)
    $total = [Math]::Max(1, ($files | Measure-Object Length -Sum).Sum)
    [long]$copied = 0
    $lastPercent = -1
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($Source.TrimEnd('\').Length).TrimStart('\')
        $target = Resolve-SafeChildPath $Destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        $copied += $file.Length
        $percent = $StartPercent + [Math]::Floor(($EndPercent - $StartPercent) * $copied / $total)
        if ($percent -ne $lastPercent) {
            Write-ProgressBar $percent "한글 실행 환경 생성 중..."
            $lastPercent = $percent
        }
    }
    Write-ProgressBar $EndPercent "한글 실행 환경 생성 완료" -Complete
}

function New-KoreanConfig {
    param(
        [string]$OriginalConfig,
        [string]$OutputConfig
    )
    $text = [IO.File]::ReadAllText($OriginalConfig)
    $autoexec = @"
[autoexec]
@echo off
mount C: ..\ARENA_KR
mount D: ..\ARENA_KR -t cdrom
C:
ARENAKR.COM
SET ARENADATA=C:
D:
ACDKR -Ssbpdig.adv -IOS220 -IRQS7 -DMAS1 -Mgenmidi.adv -IOM330 -IRQM2 -DMAM1
exit

"@
    $pattern = '(?ms)^\[autoexec\]\s*.*?(?=^\[|\z)'
    if (-not [regex]::IsMatch($text, $pattern)) { throw "arena.conf에서 [autoexec] 구역을 찾지 못했습니다." }
    $patched = [regex]::Replace($text, $pattern, $autoexec, 1)
    [IO.File]::WriteAllText($OutputConfig, $patched, (New-Object Text.UTF8Encoding($false)))
}

function Backup-TransactionFile {
    param(
        [string]$GameRoot,
        [string]$RelativePath,
        [string]$TransactionRoot,
        [System.Collections.ArrayList]$Records
    )
    $target = Resolve-SafeChildPath $GameRoot $RelativePath
    $record = [ordered]@{ relativePath = $RelativePath; existed = (Test-Path -LiteralPath $target -PathType Leaf) }
    if ($record.existed) {
        $backup = Resolve-SafeChildPath $TransactionRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
        Copy-Item -LiteralPath $target -Destination $backup -Force
    }
    $null = $Records.Add($record)
}

function Restore-Transaction {
    param(
        [string]$GameRoot,
        [string]$TransactionRoot,
        [System.Collections.ArrayList]$Records
    )
    for ($index = $Records.Count - 1; $index -ge 0; $index--) {
        $record = $Records[$index]
        $target = Resolve-SafeChildPath $GameRoot $record.relativePath
        if ($record.existed) {
            $backup = Resolve-SafeChildPath $TransactionRoot $record.relativePath
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $backup -Destination $target -Force
        } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
}

function Install-Patch {
    param(
        [string]$Root,
        [object]$Manifest,
        [switch]$Unattended
    )
    if (-not $Unattended) {
        Write-Host "게임 경로 : $Root"
        Write-Host "패치 버전 : $($Manifest.patchVersion)"
        Write-Host ""
        if ((Read-Host "설치하려면 INSTALL을 입력하십시오") -cne "INSTALL") {
            Write-Host "설치를 취소했습니다."
            return
        }
    }

    $running = @(Get-Process -Name "dosbox" -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) { throw "DOSBox가 실행 중입니다. 완전히 종료한 뒤 다시 시도하십시오." }

    $stateRoot = Join-Path $Root $StateDirectoryName
    $transactionRoot = Join-Path $stateRoot ("transactions\" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $transactionRoot | Out-Null
    $rollback = New-Object System.Collections.ArrayList
    $runtimePath = Join-Path $Root "ARENA_KR"
    $runtimeCreated = $false

    try {
        Write-ProgressBar 10 "원본 파일 검사 중..."
        foreach ($file in $Manifest.files) {
            if ($file.mode -eq "delta") {
                $source = Resolve-SafeChildPath $Root $file.source
                $delta = Resolve-SafeChildPath $PackageRoot $file.patch
                if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "원본 파일이 없습니다: $($file.source)" }
                if ((Get-Sha256 $source) -ne ([string]$file.sourceSha256).ToUpperInvariant()) {
                    throw "지원하지 않는 원본 파일입니다: $($file.source)"
                }
                if (-not (Test-Path -LiteralPath $delta -PathType Leaf) -or
                    (Get-Sha256 $delta) -ne ([string]$file.patchSha256).ToUpperInvariant()) {
                    throw "델타 파일 검증에 실패했습니다: $($file.patch)"
                }
            }
        }
        foreach ($file in $Manifest.files) {
            if ($file.mode -ne "copy") { continue }
            $payload = Resolve-SafeChildPath $PackageRoot $file.payload
            if (-not (Test-Path -LiteralPath $payload -PathType Leaf) -or
                (Get-Sha256 $payload) -ne ([string]$file.targetSha256).ToUpperInvariant()) {
                throw "배포 파일 검증에 실패했습니다: $($file.payload)"
            }
        }
        $configPath = Join-Path $Root "DOSBox-0.74\arena.conf"
        $existingConfigBackup = Join-Path $stateRoot "backup\arena.conf"
        $configSource = if (Test-Path -LiteralPath $existingConfigBackup) { $existingConfigBackup } else { $configPath }
        if ((Get-Sha256 $configSource) -ne ([string]$Manifest.config.sourceSha256).ToUpperInvariant()) {
            throw "지원하지 않거나 수정된 arena.conf입니다. 원본 복구 후 다시 시도하십시오."
        }
        Write-ProgressBar 20 "원본 및 배포 파일 검사 완료" -Complete

        if (-not (Test-Path -LiteralPath $runtimePath -PathType Container)) {
            Copy-ArenaDirectory (Join-Path $Root "ARENA") $runtimePath 20 45
            $runtimeCreated = $true
        } else {
            Write-ProgressBar 45 "기존 한글 실행 환경 유지" -Complete
        }

        $managed = @($Manifest.files)
        foreach ($file in $managed) {
            Backup-TransactionFile $Root $file.target $transactionRoot $rollback
        }
        Backup-TransactionFile $Root "DOSBox-0.74/arena.conf" $transactionRoot $rollback

        $fileCount = [Math]::Max(1, $managed.Count)
        for ($index = 0; $index -lt $managed.Count; $index++) {
            $file = $managed[$index]
            $percent = 45 + [Math]::Floor(35 * $index / $fileCount)
            Write-ProgressBar $percent ("적용 중: " + $file.target)
            $target = Resolve-SafeChildPath $Root $file.target
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            if ($file.mode -eq "delta") {
                $source = Resolve-SafeChildPath $Root $file.source
                $delta = Resolve-SafeChildPath $PackageRoot $file.patch
                Apply-ArenaDelta $source $delta $target
            } elseif ($file.mode -eq "copy") {
                $payload = Resolve-SafeChildPath $PackageRoot $file.payload
                $temporary = $target + ".new"
                Copy-Item -LiteralPath $payload -Destination $temporary -Force
                if ((Get-Sha256 $temporary) -ne ([string]$file.targetSha256).ToUpperInvariant()) {
                    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
                    throw "복사 결과 검증에 실패했습니다: $($file.target)"
                }
                Move-Item -LiteralPath $temporary -Destination $target -Force
            } else {
                throw "지원하지 않는 설치 방식입니다: $($file.mode)"
            }
        }
        Write-ProgressBar 80 "한글 파일 적용 완료" -Complete

        $backupDirectory = Join-Path $stateRoot "backup"
        $configBackup = Join-Path $backupDirectory "arena.conf"
        New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
        if (-not (Test-Path -LiteralPath $configBackup)) {
            Copy-Item -LiteralPath $configPath -Destination $configBackup
        }
        $newConfig = $configPath + ".new"
        New-KoreanConfig $configBackup $newConfig
        Move-Item -LiteralPath $newConfig -Destination $configPath -Force
        Write-ProgressBar 90 "Steam 실행 설정 연결 완료" -Complete

        $installedFiles = @()
        foreach ($file in $managed) {
            $target = Resolve-SafeChildPath $Root $file.target
            $actual = Get-Sha256 $target
            if ($actual -ne ([string]$file.targetSha256).ToUpperInvariant()) {
                throw "설치 결과 해시가 일치하지 않습니다: $($file.target)"
            }
            $installedFiles += [ordered]@{ path = $file.target; sha256 = $actual }
        }
        Write-ProgressBar 98 "최종 파일 검증 완료" -Complete

        $state = [ordered]@{
            patchVersion = $Manifest.patchVersion
            creator = $Creator
            repository = $RepositoryUrl
            installedAt = [DateTimeOffset]::Now.ToString("o")
            gameRoot = $Root
            configBackup = "backup/arena.conf"
            configPatchedSha256 = Get-Sha256 $configPath
            installedFiles = $installedFiles
        }
        $statePath = Join-Path $stateRoot "install-state.json"
        [IO.File]::WriteAllText(
            $statePath,
            ($state | ConvertTo-Json -Depth 8),
            (New-Object Text.UTF8Encoding($false))
        )
        Remove-Item -LiteralPath $transactionRoot -Recurse -Force
        Write-ProgressBar 100 "설치 상태 저장 완료" -Complete
        Write-Host ""
        Write-Host "한글 패치 설치 완료" -ForegroundColor Green
        Write-Host ""
        Write-Host "이제 Steam에서 게임을 실행하면 한글판으로 시작됩니다."
        Write-Host ""
        Write-Host "제작: $Creator"
        Write-Host "문제 제보 및 업데이트:"
        Write-Host $RepositoryUrl
    } catch {
        Write-Host ""
        Write-Host ("설치 실패: " + $_.Exception.Message) -ForegroundColor Red
        Write-Host "이번 실행에서 변경한 파일을 복구합니다."
        try {
            Restore-Transaction $Root $transactionRoot $rollback
            if ($runtimeCreated -and (Test-Path -LiteralPath $runtimePath)) {
                $expectedRuntime = [IO.Path]::GetFullPath((Join-Path $Root "ARENA_KR")).TrimEnd('\')
                if ([IO.Path]::GetFullPath($runtimePath).TrimEnd('\') -ne $expectedRuntime) {
                    throw "런타임 제거 경로 검증 실패"
                }
                Remove-Item -LiteralPath $runtimePath -Recurse -Force
            }
            Write-Ok "설치 이전 상태로 복구"
        } catch {
            Write-Host ("자동 복구 실패: " + $_.Exception.Message) -ForegroundColor Red
        }
        if (Test-Path -LiteralPath $transactionRoot) {
            Remove-Item -LiteralPath $transactionRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Test-InstalledPatch {
    param([string]$Root, [object]$Manifest)
    $statePath = Join-Path $Root "$StateDirectoryName\install-state.json"
    if (-not (Test-Path -LiteralPath $statePath)) {
        Write-Host "패치 상태: 설치되지 않음"
        return $false
    }
    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $problems = New-Object 'System.Collections.Generic.List[string]'
    foreach ($file in $Manifest.files) {
        $target = Resolve-SafeChildPath $Root $file.target
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            $problems.Add("파일 누락: $($file.target)")
        } elseif ((Get-Sha256 $target) -ne ([string]$file.targetSha256).ToUpperInvariant()) {
            $problems.Add("파일 변경됨: $($file.target)")
        }
    }
    $config = Join-Path $Root "DOSBox-0.74\arena.conf"
    if (-not (Test-Path -LiteralPath $config) -or (Get-Sha256 $config) -ne $state.configPatchedSha256) {
        $problems.Add("Steam 실행 설정이 변경됨: DOSBox-0.74/arena.conf")
    }
    if ($problems.Count -eq 0) {
        Write-Host ("패치 상태: 정상 설치 (" + $state.patchVersion + ")") -ForegroundColor Green
        return $true
    }
    Write-Host "패치 상태: 복구 필요" -ForegroundColor Yellow
    foreach ($problem in $problems) { Write-Host ("- " + $problem) }
    return $false
}

function Restore-OriginalConfig {
    param([string]$Root, [switch]$Unattended)
    if (-not $Unattended -and (Read-Host "원본 실행 설정을 복구하려면 RESTORE를 입력하십시오") -cne "RESTORE") {
        Write-Host "복구를 취소했습니다."
        return
    }
    $stateRoot = Join-Path $Root $StateDirectoryName
    $backup = Join-Path $stateRoot "backup\arena.conf"
    $config = Join-Path $Root "DOSBox-0.74\arena.conf"
    if (-not (Test-Path -LiteralPath $backup)) { throw "원본 arena.conf 백업이 없습니다." }
    $temporary = $config + ".restore"
    Copy-Item -LiteralPath $backup -Destination $temporary -Force
    Move-Item -LiteralPath $temporary -Destination $config -Force
    $state = Join-Path $stateRoot "install-state.json"
    if (Test-Path -LiteralPath $state) { Remove-Item -LiteralPath $state -Force }
    Write-Ok "원본 Steam 실행 설정 복구"
    Write-Host "ARENA_KR은 세이브 보호를 위해 그대로 보존했습니다."
}

function Update-Online {
    param([string]$Root, [object]$Manifest)
    Write-Host "GitHub에서 최신 릴리스를 확인합니다."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $headers = @{ "User-Agent" = "Arena-Korean-Patch-Installer" }
    $release = Invoke-RestMethod -Uri $LatestReleaseApi -Headers $headers -UseBasicParsing
    $latest = ([string]$release.tag_name).TrimStart('v')
    $current = [string]$Manifest.patchVersion
    Write-Host "현재 패키지: $current"
    Write-Host "최신 릴리스: $latest"
    try {
        if ([version]$latest -le [version]$current) {
            Write-Host "이미 최신 버전입니다." -ForegroundColor Green
            return
        }
    } catch {
        if ($latest -eq $current) { Write-Host "이미 최신 버전입니다."; return }
    }

    $zipAsset = $release.assets | Where-Object { $_.name -match '^Arena-Korean-Patch-v.+\.zip$' } | Select-Object -First 1
    if ($null -eq $zipAsset) { throw "업데이트 ZIP을 찾지 못했습니다." }
    $hashAsset = $release.assets | Where-Object { $_.name -eq ($zipAsset.name + ".sha256") } | Select-Object -First 1
    if ($null -eq $hashAsset) { throw "업데이트 SHA-256 파일을 찾지 못했습니다." }

    $updateRoot = Join-Path $Root "$StateDirectoryName\updates\$latest"
    New-Item -ItemType Directory -Force -Path $updateRoot | Out-Null
    $zipPath = Join-Path $updateRoot $zipAsset.name
    $hashPath = $zipPath + ".sha256"
    Write-ProgressBar 15 "최신 패치 다운로드 중..."
    Invoke-WebRequest -Uri $zipAsset.browser_download_url -Headers $headers -OutFile $zipPath -UseBasicParsing
    Invoke-WebRequest -Uri $hashAsset.browser_download_url -Headers $headers -OutFile $hashPath -UseBasicParsing
    $expected = ([regex]::Match([IO.File]::ReadAllText($hashPath), '[A-Fa-f0-9]{64}')).Value.ToUpperInvariant()
    if ([string]::IsNullOrWhiteSpace($expected) -or (Get-Sha256 $zipPath) -ne $expected) {
        throw "다운로드한 업데이트의 SHA-256이 일치하지 않습니다."
    }
    Write-ProgressBar 45 "다운로드 검증 완료" -Complete
    $extract = Join-Path $updateRoot "extracted"
    if (Test-Path -LiteralPath $extract) { Remove-Item -LiteralPath $extract -Recurse -Force }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extract -Force
    $newPatcher = Get-ChildItem -LiteralPath $extract -Recurse -Filter "patcher.ps1" -File | Select-Object -First 1
    if ($null -eq $newPatcher) { throw "업데이트 설치기를 찾지 못했습니다." }
    $newRoot = Split-Path -Parent (Split-Path -Parent $newPatcher.FullName)
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $newPatcher.FullName -PackageRoot $newRoot -AutoInstall -GamePath $Root
    if ($LASTEXITCODE -ne 0) { throw "새 설치기가 오류 코드 $LASTEXITCODE로 종료되었습니다." }
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    Write-Host "manifest.json을 찾지 못했습니다: $ManifestPath" -ForegroundColor Red
    exit 2
}
$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Header ("v" + $manifest.patchVersion)

try {
    $root = Select-ArenaRoot $GamePath
    Write-Host "게임 경로 : $root"
    Write-Host ""
    if ($AutoInstall) {
        Install-Patch $root $manifest -Unattended
        exit 0
    }
    if ($Action -eq "Install") {
        Install-Patch $root $manifest -Unattended:$Yes
        exit 0
    }
    if ($Action -eq "Status") {
        $null = Test-InstalledPatch $root $manifest
        exit 0
    }
    if ($Action -eq "Restore") {
        Restore-OriginalConfig $root -Unattended:$Yes
        exit 0
    }

    while ($true) {
        Write-Host "[1] 한글 패치 설치 또는 현재 패키지로 업데이트"
        Write-Host "[2] 최신 버전 확인 및 자동 업데이트"
        Write-Host "[3] 설치 상태 검사"
        Write-Host "[4] 원본 실행 설정 복구"
        Write-Host "[0] 종료"
        Write-Host ""
        $choice = Read-Host "실행할 작업의 번호"
        Write-Host ""
        switch ($choice) {
            "1" { Install-Patch $root $manifest }
            "2" { Update-Online $root $manifest }
            "3" { $null = Test-InstalledPatch $root $manifest }
            "4" { Restore-OriginalConfig $root }
            "0" { break }
            default { Write-Host "올바른 번호를 입력하십시오." -ForegroundColor Yellow }
        }
        if ($choice -eq "0") { break }
        Write-Host ""
        $null = Read-Host "Enter를 누르면 주 메뉴로 돌아갑니다"
        Write-Header ("v" + $manifest.patchVersion)
        Write-Host "게임 경로 : $root"
        Write-Host ""
    }
} catch {
    Write-Host ""
    Write-Host ("오류: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host ""
    Write-Host "문제 제보: $RepositoryUrl"
    exit 1
}
exit 0
