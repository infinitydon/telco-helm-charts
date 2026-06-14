{{- define "open5gs-4g.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "open5gs-4g.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "open5gs-4g.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "open5gs-4g.labels" -}}
app.kubernetes.io/name: {{ include "open5gs-4g.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
