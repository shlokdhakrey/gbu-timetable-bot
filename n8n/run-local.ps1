# Starts the n8n bot on this machine: a cloudflared tunnel for HTTPS, then n8n itself.
#
# Run it again any time the tunnel dies. The free trycloudflare URL changes every
# restart, so n8n has to be told the new one — that is the whole reason this script
# exists. n8n re-registers the Telegram webhook on boot, so nothing else to do.
#
#   powershell -ExecutionPolicy Bypass -File n8n\run-local.ps1
#
# One-time setup already done in this n8n volume (n8n_data): owner account,
# the gbu_students data table, the Telegram credential, and the published workflow.

$ErrorActionPreference = 'Stop'

$Port  = 5678
$Token = 'gbu-timetable-bot-local-dev-key'   # N8N_ENCRYPTION_KEY — must not change, or saved credentials become unreadable
$Log   = Join-Path $env:TEMP 'gbu-n8n-tunnel.log'

Write-Host '==> Docker' -ForegroundColor Cyan
try { docker info --format '{{.ServerVersion}}' | Out-Null } catch {
  Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
  Write-Host '    starting Docker Desktop, waiting...'
  do { Start-Sleep 3; $ok = $? ; try { docker info | Out-Null; $ok = $true } catch { $ok = $false } } until ($ok)
}

Write-Host '==> cloudflared tunnel' -ForegroundColor Cyan
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
if (Test-Path $Log) { Remove-Item $Log }
Start-Process cloudflared -ArgumentList "tunnel --url http://localhost:$Port --no-autoupdate" `
  -RedirectStandardError $Log -WindowStyle Hidden

$url = $null
foreach ($i in 1..40) {
  Start-Sleep 2
  if (Test-Path $Log) {
    $m = Select-String -Path $Log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
  }
}
if (-not $url) { throw "No tunnel URL after 80s. See $Log" }
Write-Host "    $url" -ForegroundColor Green

Write-Host '==> n8n' -ForegroundColor Cyan
docker rm -f n8n 2>$null | Out-Null
docker volume create n8n_data | Out-Null
docker run -d --name n8n -p "${Port}:5678" `
  -e "WEBHOOK_URL=$url/" `
  -e "N8N_HOST=$($url -replace '^https://','')" `
  -e 'N8N_PROTOCOL=https' `
  -e 'GENERIC_TIMEZONE=Asia/Kolkata' -e 'TZ=Asia/Kolkata' `
  -e "N8N_ENCRYPTION_KEY=$Token" `
  -e 'N8N_SECURE_COOKIE=false' `
  -e 'N8N_DIAGNOSTICS_ENABLED=false' `
  -e 'N8N_VERSION_NOTIFICATIONS_ENABLED=false' `
  -e 'N8N_RUNNERS_ENABLED=true' `
  -v n8n_data:/home/node/.n8n `
  docker.n8n.io/n8nio/n8n:latest | Out-Null

foreach ($i in 1..60) {
  Start-Sleep 2
  try { if ((Invoke-RestMethod "http://localhost:$Port/healthz").status -eq 'ok') { break } } catch { }
}

Write-Host ''
Write-Host "Editor:   http://localhost:$Port" -ForegroundColor Green
Write-Host "Public:   $url" -ForegroundColor Green
Write-Host ''
Write-Host 'Telegram should now point at the new URL — confirm with:'
Write-Host '  curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"'
Write-Host 'If the url there is still the old one, open the workflow and re-publish it.'
