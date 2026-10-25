param([string]$BaseUrl='http://192.168.88.165:30880',[string]$Url='https://example.com',[string]$ResultsFile='./web-results.json')
$ErrorActionPreference='Stop'
$state=Invoke-RestMethod "$BaseUrl/api/state"
$results=@()
foreach($phone in $state.phones){
 $page=Invoke-RestMethod "$BaseUrl/api/browse" -Method Post -ContentType application/json -Body (@{phone=$phone.id;url=$Url}|ConvertTo-Json) -TimeoutSec 35
 if($page.status -ne 200 -or $page.ueIp -ne $phone.internetIp -or $page.bytes -le 0 -or -not $page.text -or $page.uplinkTeid -le 0 -or $page.downlinkTeid -le 0){throw "UE $($phone.id) browsing verification failed"}
 $results+=@{phone=$phone.id;check='HTTPS through UE internet PDU session';passed=$true;ueIp=$page.ueIp;status=$page.status;bytes=$page.bytes;uplinkTeid=$page.uplinkTeid;downlinkTeid=$page.downlinkTeid}
 Write-Output "PASS $($phone.name) browsing through $($page.ueIp)"
}
if($results.Count -ne 2){throw 'Expected two UE browsing results'}
try{
 Invoke-RestMethod "$BaseUrl/api/browse" -Method Post -ContentType application/json -Body '{"phone":"1","url":"http://127.0.0.1"}' -TimeoutSec 10 | Out-Null
 throw 'Private destination was accepted'
}catch{
 if($_.ErrorDetails.Message -notlike '*private and special-use*'){throw}
 $results+=@{check='Private web destination rejected';passed=$true}
 Write-Output 'PASS private web destination rejected'
}
$results|ConvertTo-Json -Depth 5|Set-Content $ResultsFile
