param(
    [string]$Namespace = "open5gs-5g",
    [string]$Release = "open5gs-5g",
    [string]$Kubeconfig = "",
    [string]$DataEndpoint = "10.54.0.100",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$kubectlArgs = @()
if ($Kubeconfig) {
    $kubectlArgs += @("--kubeconfig", $Kubeconfig)
}
$deployment = "$Release-open5gs-5g-ue"
$dataDeployment = "$Release-open5gs-5g-data"
$webuiService = "$Release-open5gs-5g-webui"
$phoneService = "$Release-open5gs-5g-phone"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

kubectl @kubectlArgs wait --namespace $Namespace --for=condition=Available `
    "deployment/$webuiService" --timeout="${TimeoutSeconds}s"
kubectl @kubectlArgs exec --namespace $Namespace "deployment/$dataDeployment" -- `
    wget -q --spider "http://${webuiService}:9999/"
if ($LASTEXITCODE -ne 0) {
    throw "Open5GS WebUI is not reachable."
}
Write-Host "Open5GS WebUI is reachable."

kubectl @kubectlArgs wait --namespace $Namespace --for=condition=Available `
    "deployment/$deployment" --timeout="${TimeoutSeconds}s"

do {
    $logs = (kubectl @kubectlArgs logs --namespace $Namespace "deployment/$deployment" `
        --container ue --tail=150) -join "`n"
    if ($logs.Contains("PDU Session establishment is successful")) {
        Write-Host "5G registration and PDU session succeeded."
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $logs.Contains("PDU Session establishment is successful")) {
    throw "5G UE did not establish a PDU session within $TimeoutSeconds seconds."
}

kubectl @kubectlArgs exec --namespace $Namespace "deployment/$deployment" --container ue -- `
    ping -I uesimtun0 -c 5 -W 2 $DataEndpoint
if ($LASTEXITCODE -ne 0) {
    throw "5G UE could not reach the N6 test endpoint."
}

kubectl @kubectlArgs exec --namespace $Namespace "deployment/$deployment" `
    --container phone-proxy -- verify-ue-path
if ($LASTEXITCODE -ne 0) {
    throw "Phone browser proxy could not reach the Internet through uesimtun."
}

$phoneNodePort = kubectl @kubectlArgs get service --namespace $Namespace `
    $phoneService -o jsonpath='{.spec.ports[0].nodePort}'
if (-not $phoneNodePort) {
    throw "Phone UI does not have a NodePort."
}
Write-Host "Phone UI NodePort is $phoneNodePort."

Write-Host "5G end-to-end test passed."
