param(
  [string]$CoreApi = 'http://127.0.0.1:15002',
  [string]$ImsApi = 'http://127.0.0.1:15020',
  [string]$SmscApi = 'http://127.0.0.1:15010',
  [Parameter(Mandatory)][string]$CoreAddress,
  [Parameter(Mandatory)][string]$SmscAddress,
  [Parameter(Mandatory)][string]$ImsAddress,
  [string]$Email = 'lab@example.com',
  [Parameter(Mandatory)][string]$Password
)
$ErrorActionPreference = 'Stop'
function Api($Base, $Method, $Path, $Body, $Headers = @{}) {
  $p = @{Uri="$Base/api/v1/$Path"; Method=$Method; Headers=$Headers}
  if ($null -ne $Body) { $p.ContentType='application/json'; $p.Body=($Body | ConvertTo-Json -Depth 15 -Compress) }
  Invoke-RestMethod @p
}
$status = Api $CoreApi GET status $null
if ($status.result.initialized) { $auth=Api $CoreApi POST auth/login @{email=$Email;password=$Password} }
else { $auth=Api $CoreApi POST init @{email=$Email;password=$Password} }
$headers=@{Authorization="Bearer $($auth.result.token)"}
$op=Api $CoreApi GET operator $null $headers
if($op.result.id.mcc -ne '001' -or $op.result.id.mnc -ne '01') {Api $CoreApi PUT operator/id @{mcc='001';mnc='01'} $headers | Out-Null}
Api $CoreApi PUT operator/tracking @{supportedTacs=@('000001')} $headers | Out-Null
function Ensure($Path, $Name, $Body) {
  $list=Api $CoreApi GET $Path $null $headers
  if (-not ($list.result.items | Where-Object name -eq $Name)) {Api $CoreApi POST $Path $Body $headers | Out-Null}
}
Ensure profiles default @{name='default';ue_ambr_uplink='100 Mbps';ue_ambr_downlink='100 Mbps'}
Ensure slices default @{name='default';sst=1;sd='102030'}
Api $CoreApi PUT slices/default @{sst=1;sd='102030'} $headers | Out-Null
Ensure 'networking/data-networks' internet @{name='internet';ipv4_pool='10.45.0.0/16';dns='8.8.8.8';mtu=1500}
Ensure 'networking/data-networks' ims @{name='ims';ipv4_pool='10.60.0.0/16';dns='8.8.8.8';mtu=1500}
foreach($dn in @('internet','ims')) {
  $name=if($dn -eq 'internet'){'default'}else{'ims'}
  Ensure policies $name @{name=$name;profile_name='default';slice_name='default';data_network_name=$dn;session_ambr_uplink='100 Mbps';session_ambr_downlink='100 Mbps';var5qi=$(if($dn -eq 'ims'){5}else{9});arp=8}
}
Api $CoreApi PUT operator/sms @{smsNumber='+15550000000'} $headers | Out-Null
Api $CoreApi PUT operator/ims @{pcscfAddresses=@($ImsAddress)} $headers | Out-Null
$peers=Api $CoreApi GET operator/sms/smsc-peers $null $headers
$peer=@{diameterIdentity='smsc.node.epc.mnc001.mcc001.3gppnetwork.org';address=$SmscAddress;port=3868;serviceCentres=@('+15550000000')}
if($peers.result.items.Count -eq 0){Api $CoreApi POST operator/sms/smsc-peers $peer $headers | Out-Null}
else{Api $CoreApi PUT "operator/sms/smsc-peers/$($peers.result.items[0].id)" $peer $headers | Out-Null}
$operator=@{mcc='001';mnc='01';numbering=@{country_code='1';national_prefix='1';international_prefix='011'}}
Api $ImsApi PUT operator $operator | Out-Null
$smsoperator=$operator.Clone(); $smsoperator.service_centre_address='+15550000000'
Api $SmscApi PUT operator $smsoperator | Out-Null
Api $SmscApi PUT delivery @{default_validity_seconds=3600;retry_intervals_seconds=@(600)} | Out-Null
$peers=Api $ImsApi GET diameter/peers $null
$peer=@{host='';address=$CoreAddress;port=3868;transport='sctp';applications=@('cx','rx')}
if($peers.result.items.Count -eq 0){Api $ImsApi POST diameter/peers $peer | Out-Null}
else{Api $ImsApi PUT "diameter/peers/$($peers.result.items[0].id)" $peer | Out-Null}
foreach($app in @('cx','rx')) {Api $ImsApi PUT "diameter/routes/$app" @{realm='epc.mnc001.mcc001.3gppnetwork.org'} | Out-Null}
Api $ImsApi PUT policy @{interface='rx'} | Out-Null
foreach($prefix in @('7','8')) {
  foreach($n in @(100,101,200,201,300,301,400,500,501,600,700,800,900,1000,1100)) {
    $imsi='00101'+$prefix+'9'+$n.ToString('D8')
    $number=if($n -eq 600){''}else{'+1555'+$prefix+$n.ToString('D6')}
    $sub=@{imsi=$imsi;key='640f441067cd56f1474cbcacd7a0588f';opc='cb698a2341629c3241ae01de9d89de4f';sequenceNumber='000000000022';profile_name='default';msisdn=$number}
    $existing=Api $CoreApi GET "subscribers?per_page=100" $null $headers
    if(-not ($existing.result.items | Where-Object imsi -eq $imsi)){Api $CoreApi POST subscribers $sub $headers | Out-Null}
  }
}
foreach($prefix in @('7','8')) {
  foreach($n in @(1,3,4)) {
    $imsi='00101'+$prefix+'4000000'+$n.ToString('D2')
    $sub=@{imsi=$imsi;key='640f441067cd56f1474cbcacd7a0588f';opc='cb698a2341629c3241ae01de9d89de4f';sequenceNumber='000000000022';profile_name='default';msisdn=('+1555'+$prefix+'4000'+$n.ToString('D2'))}
    $existing=Api $CoreApi GET 'subscribers?per_page=100' $null $headers
    if(-not ($existing.result.items | Where-Object imsi -eq $imsi)){Api $CoreApi POST subscribers $sub $headers | Out-Null}
  }
}
Write-Output 'Core, IMS and SMSC provisioned; test subscribers created.'
