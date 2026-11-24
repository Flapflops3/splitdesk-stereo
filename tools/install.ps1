param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'SplitDeskStereo'),
    [switch]$NoShortcuts, [switch]$NoLaunch, [switch]$StartAtLogin
)
$ErrorActionPreference = 'Stop'
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64' -and $env:PROCESSOR_ARCHITEW6432 -ne 'AMD64') {throw 'This kit requires Windows x64.'}
$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dst = [IO.Path]::GetFullPath($InstallDir)
if ($src -eq $dst) {throw 'Extract the kit outside the installation folder and try again.'}
if (Test-Path "$dst/previous-output.json") {throw 'Stop the split route before upgrading.'}
if ((Get-Process -Name SplitDeskTray -ErrorAction SilentlyContinue) -or
    (Get-Process | Where-Object MainWindowTitle -eq 'SplitDesk · Stereo Mixer')) {throw 'Close the mixer and choose Quit Tray before upgrading.'}
New-Item -ItemType Directory -Path $dst,"$dst/mixer" -Force | Out-Null
$uvCmd = Get-Command uv.exe -ErrorAction SilentlyContinue
if ($uvCmd) { $uvPath=$uvCmd.Source }
else {
    $cache=Join-Path $env:LOCALAPPDATA 'SplitDeskTools/uv-0.13.9'
    New-Item -ItemType Directory $cache -Force | Out-Null
    $zip=Join-Path $cache 'uv.zip'
    $uri='https://github.com/astral-sh/uv/releases/download/0.13.9/uv-x86_64-pc-windows-msvc.zip'
    Invoke-WebRequest -UseBasicParsing $uri -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne 'EDD61F7F5728A56CC62455386661860BDFC7BAB65872F39B0C25BDCC1D8E1BEB') {throw 'uv archive checksum mismatch'}
    Expand-Archive $zip -DestinationPath $cache -Force
    $uvPath=(Get-ChildItem $cache -Recurse -Filter 'uv.exe' | Select-Object -First 1).FullName
}
if (!(Test-Path "$dst/venv/Scripts/python.exe")) {
    & $uvPath venv --python 3.14 --managed-python "$dst/venv"
    if ($LASTEXITCODE) {throw 'Python environment setup failed.'}
}
& $uvPath pip install --python "$dst/venv/Scripts/python.exe" --only-binary :all: -r "$src/requirements.txt"
if ($LASTEXITCODE) {throw 'Python dependencies failed to install.'}
foreach ($f in 'launch.py','devices.py','router.py','audio_tone.py','requirements.txt','README.md','LICENSE','NOTICE.md','Check.cmd','Stop.cmd','Test stereo.wav') {
    Copy-Item -LiteralPath "$src/$f" -Destination $dst -Force
}
Copy-Item "$src/mixer/*" -Include '*.py','*.dll','*.exe','*.jpg','*.ico' -Destination "$dst/mixer" -Force
Copy-Item "$src/docs" -Destination $dst -Recurse -Force
if (!$NoShortcuts) {
    $shell=New-Object -ComObject WScript.Shell
    function Shortcut($folder,$arguments) {
        $link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath($folder)) 'SplitDesk Stereo.lnk'))
        $link.TargetPath="$dst/mixer/SplitDeskTray.exe"
        $link.Arguments=$arguments
        $link.WorkingDirectory=$dst
        $link.IconLocation="$dst/mixer/walnut.ico,0"
        $link.Save()
    }
    Shortcut 'Desktop' '/open'
    if ($StartAtLogin) {Shortcut 'Startup' ''}
}
Write-Host "Installed at $dst"
if (!$NoLaunch) {Start-Process "$dst/mixer/SplitDeskTray.exe" -ArgumentList '/open'}
