param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$homeDir = "D:\AshenToons\control-room"
$python = "D:\AshenToons\tools\.venv-memanga\Scripts\python.exe"
$serverFile = Join-Path $homeDir "server.py"
$crewFile = Join-Path $homeDir "crew_worker.py"
$browserUrl = "http://127.0.0.1:8770/open"

function Has-Port([int]$port) {
  return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
function Has-Crew() {
  $running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*AshenToons*control-room*crew_worker.py*" })
  return $running.Count -gt 0
}
if(-not (Test-Path -LiteralPath $python)) { throw "AshenToons Python environment missing" }
foreach($file in @($serverFile, $crewFile)) {
  if(-not (Test-Path -LiteralPath $file)) { throw "Missing file: $file" }
}
if(-not (Has-Port 11434)) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if($ollama) {
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WorkingDirectory $homeDir -WindowStyle Hidden
    for($i=0;$i -lt 16;$i++) {
      Start-Sleep -Milliseconds 400
      if(Has-Port 11434) { break }
    }
  }
}
if(-not (Has-Port 8770)) {
  Start-Process -FilePath $python -ArgumentList @("-u", ('"'+$serverFile+'"'), "--serve") -WorkingDirectory $homeDir -WindowStyle Hidden
  for($i=0;$i -lt 20;$i++) {
    Start-Sleep -Milliseconds 400
    if(Has-Port 8770) { break }
  }
}
if(-not (Has-Port 8770)) { throw "Control Room server could not be started on port 8770" }
if(-not (Has-Crew)) {
  Start-Process -FilePath $python -ArgumentList @("-u", ('"'+$crewFile+'"')) -WorkingDirectory $homeDir -WindowStyle Hidden
  Start-Sleep -Seconds 1
}
if(-not $NoBrowser) { Start-Process $browserUrl }
Write-Output "ASHENTOONS_HQ_READY=$browserUrl"
Write-Output ("LOCAL_CREW_RUNNING="+(Has-Crew))
Write-Output ("OLLAMA_RUNNING="+(Has-Port 11434))
Write-Output ("SOURCE_DRIVE_LABEL="+(Get-Volume -DriveLetter D).FileSystemLabel)
