{{- define "open5gs-5g.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "open5gs-5g.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "open5gs-5g.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "open5gs-5g.labels" -}}
app.kubernetes.io/name: {{ include "open5gs-5g.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
