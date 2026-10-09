$ErrorActionPreference = "Stop"
$exe = "D:\AshenToons\tools\.venv-memanga\Scripts\python.exe"
$script = "D:\AshenToons\control-room\voice_setup.py"
$url = "http://127.0.0.1:8771/"
if(-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $script)) {
  Write-Host "AshenToons voice setup files are missing."
  exit 1
}
$already = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue
if(-not $already) {
  Start-Process -FilePath $exe -ArgumentList @("-u", $script) -WorkingDirectory "D:\AshenToons\control-room" -WindowStyle Hidden
  for($i=0;$i -lt 12;$i++){
    Start-Sleep -Milliseconds 250
    if(Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue){break}
  }
}
Start-Process $url
Write-Host "Opening the private Google voice key setup on this laptop. Do not paste keys into ChatGPT."
