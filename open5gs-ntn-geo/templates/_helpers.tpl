{{- define "ntn.name" -}}{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "ntn.fullname" -}}{{- printf "%s-%s" .Release.Name (include "ntn.name" .) | trunc 63 | trimSuffix "-" -}}{{- end -}}
{{- define "ntn.labels" -}}
app.kubernetes.io/name: {{ include "ntn.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/part-of: open5gs-ntn-{{ .Values.oai.scenario }}
{{- end -}}
