param(
    [string]$Namespace = "open5gs-5g-dra",
    [string]$Release = "dra5g",
    [string]$Kubeconfig = "",
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"
$kubectlArgs = @()
if ($Kubeconfig) {
    $kubectlArgs += @("--kubeconfig", $Kubeconfig)
}

$prefix = "$Release-open5gs-5g-dra"
$ueDeployment = "$prefix-ue"
$gnbDeployment = "$prefix-gnb"
$upfDeployment = "$prefix-upf"
$dataDeployment = "$prefix-data"
$webuiService = "$prefix-webui"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

kubectl @kubectlArgs wait --namespace $Namespace --for=condition=Available `
    "deployment/$webuiService" --timeout="${TimeoutSeconds}s"
kubectl @kubectlArgs exec --namespace $Namespace "deployment/$dataDeployment" -- `
    wget -q --spider "http://${webuiService}:9999/"
if ($LASTEXITCODE -ne 0) {
    throw "Open5GS WebUI is not reachable."
}
Write-Host "Open5GS WebUI is reachable."

kubectl @kubectlArgs exec --namespace $Namespace "deployment/$gnbDeployment" -- `
    sh -ec "ip link show n2 >/dev/null; ip link show n3 >/dev/null"
kubectl @kubectlArgs exec --namespace $Namespace "deployment/$upfDeployment" -- `
    sh -ec "ip link show n3 >/dev/null; ip link show n4 >/dev/null; ip link show n6 >/dev/null"
kubectl @kubectlArgs exec --namespace $Namespace "deployment/$dataDeployment" -- `
    sh -ec "ip link show n6 >/dev/null"
if ($LASTEXITCODE -ne 0) {
    throw "One or more protocol-named DRA interfaces are missing."
}

$unexpected = (kubectl @kubectlArgs exec --namespace $Namespace `
    "deployment/$upfDeployment" -- sh -ec `
    "ip -o link show | grep -E ': net[0-9]+:' || true") -join "`n"
if ($unexpected) {
    throw "Unexpected netN interface found: $unexpected"
}
Write-Host "DRA interfaces use protocol names only."

kubectl @kubectlArgs wait --namespace $Namespace --for=condition=Available `
    "deployment/$ueDeployment" --timeout="${TimeoutSeconds}s"

do {
    $logs = (kubectl @kubectlArgs logs --namespace $Namespace `
        "deployment/$ueDeployment" --container ue --tail=150) -join "`n"
    if ($logs.Contains("PDU Session establishment is successful")) {
        Write-Host "5G registration and PDU session succeeded."
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $logs.Contains("PDU Session establishment is successful")) {
    throw "5G UE did not establish a PDU session within $TimeoutSeconds seconds."
}

kubectl @kubectlArgs exec --namespace $Namespace "deployment/$ueDeployment" `
    --container tools -- ping -I uesimtun0 -c 5 -W 2 10.60.0.60
if ($LASTEXITCODE -ne 0) {
    throw "5G UE could not reach the DRA N6 test endpoint."
}

kubectl @kubectlArgs exec --namespace $Namespace "deployment/$ueDeployment" `
    --container tools -- iperf3 -c 10.60.0.60 --bind-dev uesimtun0 -t 5
if ($LASTEXITCODE -ne 0) {
    throw "iperf3 failed through the UE PDU-session interface."
}

Write-Host "5G DRA end-to-end ping and iperf3 tests passed."
