$ErrorActionPreference = 'Stop'
$sdkRoot = $env:ANDROID_HOME
if (-not $sdkRoot) { $sdkRoot = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
$emulator = Join-Path $sdkRoot 'emulator\emulator.exe'
$avd = 'AstroWeb_Google_TV'
$serial = 'emulator-5580'
function Find-AstroWebEmulator {
    foreach ($line in (& $adb devices)) {
        if ($line -match '^(emulator-\d+)\s+device$') {
            $candidate = $Matches[1]
            if ((& $adb -s $candidate emu avd name 2>$null | ForEach-Object { $_.Trim() }) -contains $avd) { return $candidate }
        }
    }
}
$running = Find-AstroWebEmulator
if ($running) { $serial = $running }
else {
    if ((& $emulator -list-avds) -notcontains $avd) { throw "Maak eerst de AVD $avd. Zie tv/README.md." }
    if ((& $adb devices) -match "^$serial\s") { throw "Emulatorpoort 5580 is bezet. Start $avd in Android Studio en probeer opnieuw." }
    $avdRoot = $env:ANDROID_AVD_HOME
    if (-not $avdRoot) { $avdRoot = Join-Path $env:USERPROFILE '.android\avd' }
    $descriptor = Join-Path $avdRoot "$avd.ini"
    $bootArgs = @('-avd',$avd,'-port','5580')
    if (Test-Path -LiteralPath $descriptor) {
        $line = Get-Content -LiteralPath $descriptor | Where-Object { $_ -match '^path=' } | Select-Object -First 1
        if ($line) {
            $config = Join-Path $line.Substring(5) 'config.ini'
            $settings = [IO.File]::ReadAllText($config)
            if ($settings -notmatch '(?m)^hw\.keyboard\s*=\s*yes\s*$') {
                if ($settings -match '(?m)^hw\.keyboard\s*=') {
                    $settings = $settings -replace '(?m)^hw\.keyboard\s*=[^\r\n]*','hw.keyboard=yes'
                } else { $settings += [Environment]::NewLine + 'hw.keyboard=yes' + [Environment]::NewLine }
                [IO.File]::WriteAllText($config,$settings)
                $bootArgs += '-no-snapshot-load'
            }
        }
    }
    Start-Process -FilePath $emulator -ArgumentList $bootArgs
}
$ready = $false
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
    if ((& $adb -s $serial shell getprop sys.boot_completed 2>$null) -eq '1') { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'De Google TV-emulator is nog niet klaar.' }
$package = 'nl.ronamersfoort.astroweb.tv'
if (-not (& $adb -s $serial shell pm path $package)) {
    $apk = Join-Path $PSScriptRoot 'app\build\outputs\apk\debug\app-debug.apk'
    if (-not (Test-Path -LiteralPath $apk)) { throw 'Bouw eerst de APK met gradlew.bat assembleDebug. Zie tv/README.md.' }
    & $adb -s $serial install -r $apk
    if ($LASTEXITCODE) { throw 'De APK kon niet worden geïnstalleerd.' }
}
& $adb -s $serial shell am start -W -n "$package/.MainActivity"
exit $LASTEXITCODE
