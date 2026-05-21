{{- define "ueransim.name" -}}
ueransim
{{- end }}

{{- define "ueransim.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ueransim.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "ueransim.namespace" -}}
{{ .Release.Namespace }}
{{- end }}
