param(
    [string]$Namespace = "open5gs-4g",
    [string]$Release = "open5gs-4g",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$deployment = "$Release-open5gs-4g-simulator"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

kubectl wait --namespace $Namespace --for=condition=Available `
    "deployment/$deployment" --timeout="${TimeoutSeconds}s"

do {
    $logs = (kubectl logs --namespace $Namespace "deployment/$deployment" `
        --container ue --tail=150) -join "`n"
    if ($logs.Contains("Network attach successful")) {
        Write-Host "LTE attach succeeded."
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $logs.Contains("Network attach successful")) {
    throw "LTE UE did not attach within $TimeoutSeconds seconds."
}

kubectl exec --namespace $Namespace "deployment/$deployment" --container ue `
    -- ping -I tun_srsue -c 5 -W 2 10.55.0.100
if ($LASTEXITCODE -ne 0) {
    throw "LTE UE could not reach the SGi test endpoint."
}

Write-Host "4G end-to-end test passed."
