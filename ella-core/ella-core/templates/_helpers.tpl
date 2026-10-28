{{- define "core.fullname" -}}
{{- default (printf "%s-core" .Release.Name) .Values.fullnameOverride -}}
{{- end -}}
{{- define "core.count" -}}
{{- if eq .Values.topology "ha" -}}{{ .Values.replicaCount }}{{- else -}}1{{- end -}}
{{- end -}}
{{- define "core.network" -}}
{{- $local := deepCopy .Values.network -}}
{{- $global := deepCopy ((.Values.global | default dict).network | default dict) -}}
{{- $network := mergeOverwrite $local $global -}}
{{- $n6 := deepCopy ($network.n6 | default dict) -}}
{{- range $old, $new := dict "coreAddresses" "coreAddresses" "gateway" "gatewayAddress" "imsAddress" "imsAddress" "smscAddress" "smscAddress" -}}
  {{- if hasKey $local $old }}{{- $_ := set $n6 $new (index $local $old) }}{{- end -}}
  {{- if hasKey $global $old }}{{- $_ := set $n6 $new (index $global $old) }}{{- end -}}
{{- end -}}
{{- $dnnPools := deepCopy ($network.dnnPools | default dict) -}}
{{- range $old, $new := dict "internetPool" "internet" "imsPool" "ims" -}}
  {{- if hasKey $local $old }}{{- $_ := set $dnnPools $new (index $local $old) }}{{- end -}}
  {{- if hasKey $global $old }}{{- $_ := set $dnnPools $new (index $global $old) }}{{- end -}}
{{- end -}}
{{- $n2n3 := deepCopy ($network.n2n3 | default dict) -}}
{{- if and (hasKey $local "n2n3") (hasKey $local.n2n3 "coreAddresses") }}{{- $_ := set $n2n3 "coreInterfaceAddresses" $local.n2n3.coreAddresses }}{{- end -}}
{{- if and (hasKey $global "n2n3") (hasKey $global.n2n3 "coreAddresses") }}{{- $_ := set $n2n3 "coreInterfaceAddresses" $global.n2n3.coreAddresses }}{{- end -}}
{{- $_ := set $network "n6" $n6 -}}
{{- $_ := set $network "dnnPools" $dnnPools -}}
{{- $_ := set $network "n2n3" $n2n3 -}}
{{- toJson $network -}}
{{- end -}}
{{- define "core.n6GatewayEnabled" -}}
{{- or .Values.n6Gateway.enabled .Values.controller.gatewayEnabled -}}
{{- end -}}
{{- define "core.labels" -}}
app.kubernetes.io/name: ella-core
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "core.serviceSelector" -}}
{{- $root := .root -}}
{{- $pod := printf "%s-0" (include "core.fullname" $root) -}}
{{- $existing := lookup "v1" "Service" $root.Release.Namespace .service -}}
{{- if and $root.Values.controller.enabled $existing -}}
{{- $pod = default $pod (index ($existing.spec.selector | default dict) "statefulset.kubernetes.io/pod-name") -}}
{{- end -}}
{{ include "core.labels" $root }}
statefulset.kubernetes.io/pod-name: {{ $pod }}
{{- end -}}
