param(
    [string]$Namespace = "open5gs-5g",
    [string]$Release = "open5gs-5g",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$deployment = "$Release-open5gs-5g-ue"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

kubectl wait --namespace $Namespace --for=condition=Available `
    "deployment/$deployment" --timeout="${TimeoutSeconds}s"

do {
    $logs = (kubectl logs --namespace $Namespace "deployment/$deployment" `
        --tail=150) -join "`n"
    if ($logs.Contains("PDU Session establishment is successful")) {
        Write-Host "5G registration and PDU session succeeded."
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $logs.Contains("PDU Session establishment is successful")) {
    throw "5G UE did not establish a PDU session within $TimeoutSeconds seconds."
}

kubectl exec --namespace $Namespace "deployment/$deployment" -- `
    ping -I uesimtun0 -c 5 -W 2 10.54.0.100
if ($LASTEXITCODE -ne 0) {
    throw "5G UE could not reach the N6 test endpoint."
}

Write-Host "5G end-to-end test passed."
