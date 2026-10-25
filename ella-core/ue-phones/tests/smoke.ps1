param([string]$BaseUrl='http://127.0.0.1:18080',[string]$ResultsFile='./phone-results.json')
$ErrorActionPreference='Stop'
$checks=[Collections.Generic.List[object]]::new()
function State {Invoke-RestMethod "$BaseUrl/api/state"}
function Act($Phone,$Action,$Extra=@{}) {
 $body=@{phone=$Phone;action=$Action}+$Extra
 Invoke-RestMethod "$BaseUrl/api/action" -Method Post -ContentType application/json -Body ($body|ConvertTo-Json) | Out-Null
}
function Await($Name,[scriptblock]$Check,[int]$Seconds=30){
 $limit=[DateTime]::UtcNow.AddSeconds($Seconds)
 do{$s=State;if(&$Check $s){$checks.Add(@{check=$Name;passed=$true});Write-Output "PASS $Name";return};Start-Sleep -Milliseconds 400}while([DateTime]::UtcNow -lt $limit)
 throw "Timed out: $Name"
}
try {
 Await 'Both UEs attached with NAS SMS' {param($s) $s.ready -and $s.phones.Count -eq 2 -and @($s.phones|Where-Object {-not $_.nas}).Count -eq 0} 90
 foreach($id in @('1','2')) {Act $id register}
 Await 'Both UEs IMS registered' {param($s) @($s.phones|Where-Object registered).Count -eq 2}
 $textA='Hello from Phone A '+[DateTime]::UtcNow.ToString('HHmmss')
 Act '1' sms @{to='+15558400004';text=$textA}
 Await 'NAS SMS A to B received and delivered' {param($s) @($s.phones[1].messages|Where-Object {$_.direction -eq 'received' -and $_.text -eq $textA}).Count -gt 0 -and @($s.phones[0].messages|Where-Object {$_.text -eq $textA -and $_.status -eq 'delivered to UE'}).Count -gt 0}
 $textB='Hi A, ça va? € '+[DateTime]::UtcNow.ToString('HHmmss')
 Act '2' sms @{to='+15558400003';text=$textB}
 Await 'NAS SMS B to A, accented text intact' {param($s) @($s.phones[0].messages|Where-Object {$_.direction -eq 'received' -and $_.text -eq $textB}).Count -gt 0}
 foreach($direction in @(@('1','2','+15558400004'),@('2','1','+15558400003'))) {
  $from=$direction[0];$to=$direction[1];$label="$from to $to"
  Act $from call @{to=$direction[2]}
  Await "IMS incoming call $label" {param($s) $p=$s.phones|Where-Object id -eq $to;$p.incoming -and $p.call -eq 'early'}
  Act $to answer
  Await "IMS call $label confirmed, bidirectional voice QFI media" {param($s) @($s.phones|Where-Object {$_.call -eq 'confirmed' -and $_.tx -gt 5 -and $_.rx -gt 5 -and $_.qfi -is [array] -and $_.qfi.Count -gt 0}).Count -eq 2}
  Act $from hangup
  Await "IMS call $label released" {param($s) @($s.phones|Where-Object call -eq terminated).Count -eq 2}
 }
 Act '1' unregister
 Await 'Phone A IMS deregistration' {param($s) -not $s.phones[0].registered -and $s.phones[1].registered}
 Act '1' register
 Await 'Phone A IMS reregistration' {param($s) $s.phones[0].registered}
 $checks|ConvertTo-Json -Depth 5|Set-Content $ResultsFile
 Write-Output "$($checks.Count) checks passed"
} catch {
 $checks.Add(@{check=$_.Exception.Message;passed=$false})
 $checks|ConvertTo-Json -Depth 5|Set-Content $ResultsFile
 throw
}
