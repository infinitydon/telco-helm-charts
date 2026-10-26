{{- define "core.fullname" -}}
{{- default (printf "%s-core" .Release.Name) .Values.fullnameOverride -}}
{{- end -}}
{{- define "core.count" -}}
{{- if eq .Values.topology "ha" -}}{{ .Values.replicaCount }}{{- else -}}1{{- end -}}
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
