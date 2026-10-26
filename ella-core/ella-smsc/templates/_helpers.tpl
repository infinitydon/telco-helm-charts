{{- define "ella-smsc.name" -}}
{{- printf "%s-%s" .Release.Name "ella-smsc" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "ella-smsc.selector" -}}
app.kubernetes.io/name: {{ "ella-smsc" }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "ella-smsc.labels" -}}
{{ include "ella-smsc.selector" . }}
helm.sh/chart: {{ printf "%s-%s" "ella-smsc" .Chart.Version | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
