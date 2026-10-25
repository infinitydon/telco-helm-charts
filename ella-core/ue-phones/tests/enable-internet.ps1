param(
 [string]$Namespace='ella-services-test',
 [ValidatePattern('^[0-9.]+$')][string]$Gateway='10.6.0.1',
 [ValidatePattern('^[0-9./]+$')][string]$UePool='10.45.0.0/16',
 [ValidatePattern('^[a-zA-Z0-9_.:-]+$')][string]$N6Interface='net2'
)
$ErrorActionPreference='Stop'
$core=(kubectl -n $Namespace get pod -l app=ella-core-lab -o json|ConvertFrom-Json).items[0]
if(-not $core){throw 'Ella Core lab pod not found'}
$name='ue-internet-route'
$configure="ip route replace default via $Gateway dev $N6Interface table 200; ip rule show | grep -Fq 'from $UePool lookup 200' || ip rule add priority 1200 from $UePool table 200"
$containers=@($core.spec.containers)+@($core.spec.ephemeralContainers)
if($containers|Where-Object name -eq $name){
 kubectl -n $Namespace exec $core.metadata.name -c $name -- /bin/bash -ec $configure
}else{
 # Add a network helper without restarting Core or its ephemeral database.
 kubectl -n $Namespace debug "pod/$($core.metadata.name)" --container=$name --image=ghcr.io/ellanetworks/ubuntu-router:0.1 --profile=sysadmin --attach=false -- /bin/bash -ec "$configure; exec sleep infinity"
}
if($LASTEXITCODE -ne 0){throw 'Core internet source-route configuration failed'}
Write-Output 'Core UE internet source route configured. Core API/Diameter routes are unchanged.'
