$questions = Get-Content `
    "C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel\test_questions.json" `
    -Raw | ConvertFrom-Json

$logFile = "C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel\step5_full_log.txt"

"" | Set-Content $logFile -Encoding utf8

$questions | Where-Object { $_.id -le 19 } | ForEach-Object {

    $sid = "step5_q$($_.id)_$(Get-Random)"

    Write-Host ""
    Write-Host "=================================================="
    Write-Host "Q$($_.id): $($_.question)"
    Write-Host "SESSION: $sid"
    Write-Host "=================================================="

    $body = @{
        session_id = $sid
        user_message = [string]$_.question
    } | ConvertTo-Json -Depth 10

    try {
        $result = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8000/chat" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body

        Write-Host "RESPONSE:"
        Write-Host $result.response
    }
    catch {
        Write-Host "ERROR:"
        Write-Host $_.Exception.Message
    }

}  | Tee-Object -FilePath $logFile

Write-Host ""
Write-Host "=================================================="
Write-Host "Q1-Q19 TEST RUN COMPLETE"
Write-Host "LOG FILE:"
Write-Host $logFile
Write-Host "=================================================="