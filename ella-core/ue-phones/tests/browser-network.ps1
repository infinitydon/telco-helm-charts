param([string]$Kubeconfig="$HOME/.kube/ebng-cp--kubeconfig",[string]$Namespace='ella-services-test',[string]$ResultsFile='./browser-network-results.json')
$ErrorActionPreference='Stop'
$results=[Collections.Generic.List[object]]::new()
function Run-Curl($Deployment,[switch]$Direct){
 $args=@('--kubeconfig',$Kubeconfig,'-n',$Namespace,'exec',"deployment/$Deployment",'-c','browser','--','curl','-fsS','--connect-timeout','3','--max-time','10','-o','/dev/null','-w','%{http_code}')
 if($Direct){$args+=@('--noproxy','*','https://1.1.1.1')}else{$args+=@('--socks5-hostname','127.0.0.1:1080','https://example.com')}
 $output=& kubectl @args 2>&1
 return @{code=$LASTEXITCODE;output=($output -join "`n")}
}
foreach($deployment in @('ue-ue-a','ue-ue-b')){
 $r=Run-Curl $deployment
 if($r.code -ne 0 -or $r.output -notlike '*200*'){throw "Proxy fetch failed: $deployment $($r.output)"}
 $results.Add(@{check="$deployment HTTPS through UE proxy";passed=$true})
 $r=Run-Curl $deployment -Direct
 if($r.code -eq 0){throw "Direct browser egress was allowed: $deployment"}
 $rules=& kubectl --kubeconfig $Kubeconfig -n $Namespace exec "deployment/$deployment" -c phone -- iptables -nvL ELLA_BROWSER
 $rejected=@($rules|Where-Object {$_ -match '^\s*([1-9][0-9]*)\s+\S+\s+REJECT'})
 if($LASTEXITCODE -ne 0 -or $rejected.Count -eq 0){throw "No firewall rejection counter for $deployment"}
 $results.Add(@{check="$deployment direct browser egress blocked";passed=$true})
}
try{
 & kubectl --kubeconfig $Kubeconfig -n $Namespace exec deployment/ue-ue-a -c phone -- ip link set ellaweb0 down
 if($LASTEXITCODE -ne 0){throw 'Could not suspend UE A internet tunnel'}
 $r=Run-Curl ue-ue-a
 if($r.code -eq 0){throw 'UE A proxy bypassed its disconnected tunnel'}
 $results.Add(@{check='UE A cannot browse with its internet tunnel down';passed=$true})
 $r=Run-Curl ue-ue-b
 if($r.code -ne 0 -or $r.output -notlike '*200*'){throw 'UE B was affected by UE A tunnel interruption'}
 $results.Add(@{check='UE B continues browsing while UE A tunnel is down';passed=$true})
}finally{
 & kubectl --kubeconfig $Kubeconfig -n $Namespace exec deployment/ue-ue-a -c phone -- ip link set ellaweb0 up
 if($LASTEXITCODE -ne 0){throw 'Could not restore UE A internet tunnel'}
 & kubectl --kubeconfig $Kubeconfig -n $Namespace exec deployment/ue-ue-a -c phone -- ip route replace default dev ellaweb0 table 200
 if($LASTEXITCODE -ne 0){throw 'Could not restore UE A source route'}
}
$r=Run-Curl ue-ue-a
if($r.code -ne 0 -or $r.output -notlike '*200*'){throw 'UE A browsing did not recover'}
$results.Add(@{check='UE A browsing recovered after restoring its tunnel';passed=$true})
$results|ConvertTo-Json -Depth 4|Set-Content $ResultsFile
$results|ForEach-Object {Write-Output "PASS $($_.check)"}
