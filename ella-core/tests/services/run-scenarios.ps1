param(
  [string]$Namespace='ella-services-test',
  [string]$CoreApi='http://127.0.0.1:25002',
  [string]$Email='lab@example.com',
  [Parameter(Mandatory)][string]$Password,
  [string]$OutputDirectory='./results',
  [string[]]$Scenarios=@('sms/5g_mo_mt','sms/4g_mo_mt','sms/5g_idle_recipient','sms/4g_idle_recipient','sms/5g_injected','sms/4g_injected','sms/5g_memory_full','sms/4g_memory_full','sms/5g_switched_off','sms/4g_switched_off','sms/5g_back_to_back','sms/4g_back_to_back','sms/5g_unserved_service_centre','sms/4g_unserved_service_centre','sms/5g_not_granted','sms/4g_not_granted','ims/5g_registration','ims/5g_call','ims/4g_registration','ims/4g_call')
)
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$core=(kubectl -n $Namespace get pod -l app=ella-core-lab -o json | ConvertFrom-Json).items[0]
$tester=kubectl -n $Namespace get pod ella-services-tester -o json | ConvertFrom-Json
$net=$tester.metadata.annotations.'k8s.v1.cni.cncf.io/network-status' | ConvertFrom-Json
$n3=($net | Where-Object interface -eq net1).ips[0]
$login=Invoke-RestMethod "$CoreApi/api/v1/auth/login" -Method Post -ContentType application/json -Body (@{email=$Email;password=$Password}|ConvertTo-Json)
$result=@()
foreach($scenario in $Scenarios) {
  $port=if($scenario -match '/4g_'){36412}else{38412}
  $arguments=@('run',$scenario,'--ella-core-n2-address',"$($core.status.podIP):$port",'--gnb',"lab,n2=$($tester.status.podIP),n3=$n3",'--ip-version','ipv4','--ella-api-address','http://ella-core-lab:5002','--ella-api-token',$login.result.token)
  if($scenario -like 'sms/*'){$arguments+=@('--smsc-api-address','http://smsc-ella-smsc:5010')}
  $log=Join-Path $OutputDirectory ($scenario.Replace('/','-')+'.log')
  kubectl -n $Namespace exec ella-services-tester -- core-tester @arguments *> $log
  $code=$LASTEXITCODE
  $result+=@{scenario=$scenario;exitCode=$code;passed=($code -eq 0)}
  Write-Output "$scenario exit=$code"
  $result | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $OutputDirectory 'results.json')
}
if($result | Where-Object { -not $_.passed }){exit 1}
