Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess | Format-Table -AutoSize

echo "API   : $(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8000/health)  $(curl -s -m 5 http://127.0.0.1:8000/health)"; echo "UI    : $(curl -s -o /dev/null -w '%{http_code}' -m 5 http://localhost:8501)  $(curl -s -m 5 http://localhost:8501/_stcore/health)"


Start-Process "http://localhost:8501"; Write-Output "opened http://localhost:8501"