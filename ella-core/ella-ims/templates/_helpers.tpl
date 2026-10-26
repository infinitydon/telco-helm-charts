{{- define "ella-ims.name" -}}
{{- printf "%s-%s" .Release.Name "ella-ims" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "ella-ims.selector" -}}
app.kubernetes.io/name: {{ "ella-ims" }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "ella-ims.labels" -}}
{{ include "ella-ims.selector" . }}
helm.sh/chart: {{ printf "%s-%s" "ella-ims" .Chart.Version | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
