param(
 [ValidateSet('ClusterIP','NodePort','LoadBalancer')][string]$ServiceType='NodePort',
 [ValidateRange(0,65535)][int]$NodePort=30502,
 [ValidateRange(1,65535)][int]$Port=5002,
 [ValidateRange(1,65535)][int]$TargetPort=5002,
 [string]$Namespace='ella-services-test',
 [string]$Kubeconfig=''
)
$ErrorActionPreference='Stop'
$servicePort=@{name='http';port=$Port;targetPort=$TargetPort;protocol='TCP'}
if($ServiceType -ne 'ClusterIP' -and $NodePort -gt 0){$servicePort.nodePort=$NodePort}
$service=@{apiVersion='v1';kind='Service';metadata=@{name='ella-core-lab';namespace=$Namespace};spec=@{type=$ServiceType;selector=@{app='ella-core-lab'};ports=@($servicePort)}}
$kubectlArgs=@()
if($Kubeconfig){$kubectlArgs+=@('--kubeconfig',$Kubeconfig)}
$service|ConvertTo-Json -Depth 8|& kubectl @kubectlArgs apply -f -
if($LASTEXITCODE -ne 0){throw 'Core UI Service configuration failed'}
& kubectl @kubectlArgs -n $Namespace get service ella-core-lab
if($LASTEXITCODE -ne 0){throw 'Could not read Core UI Service'}
