{{- define "ella-core.name" -}}
ella-core
{{- end }}

{{- define "ella-core.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ella-core.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "ella-core.serviceName" -}}
ella-core
{{- end }}

{{- define "ella-core.namespace" -}}
{{ .Release.Namespace }}
{{- end }}

{{- /*
  Compute expected N2 IP for a given pod index.
  Whereabouts assigns IPs sequentially from rangeStart based on pod name,
  so pod ella-core-{idx} gets rangeStart + idx.
  Usage: {{ include "ella-core.n2ip" (dict "root" . "idx" 2) }}
*/ -}}
{{- define "ella-core.n2ip" -}}
{{- $baseOctet := regexFind "[0-9]+$" .root.Values.multus.n2.rangeStart | int -}}
{{- $ipOctet := add $baseOctet .idx -}}
{{- regexReplaceAll "[0-9]+$" .root.Values.multus.n2.rangeStart ($ipOctet | toString) -}}
{{- end -}}
