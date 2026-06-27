param(
    [string]$Namespace = "magma-ebpf-test",
    [string]$Release = "magma-ebpf",
    [string]$Kubeconfig = "",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$chartDir = Split-Path -Parent $PSScriptRoot
$kubectlArgs = @()
$helmArgs = @()
if ($Kubeconfig) {
    $kubectlArgs += @("--kubeconfig", $Kubeconfig)
    $helmArgs += @("--kubeconfig", $Kubeconfig)
}

helm @helmArgs lint $chartDir
helm @helmArgs template $Release $chartDir --no-hooks | kubectl @kubectlArgs apply --dry-run=server -f -

if (-not $SkipInstall) {
    kubectl @kubectlArgs create namespace $Namespace --dry-run=client -o yaml | kubectl @kubectlArgs apply -f -
    helm @helmArgs upgrade --install $Release $chartDir --namespace $Namespace --wait
    helm @helmArgs test $Release --namespace $Namespace --logs
    helm @helmArgs uninstall $Release --namespace $Namespace
    kubectl @kubectlArgs delete namespace $Namespace --wait=false
}

Write-Host "magma-ebpf chart validation passed."
