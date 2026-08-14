{{- define "n2lab.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "n2lab.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "n2lab.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "n2lab.labels" -}}
app.kubernetes.io/name: {{ include "n2lab.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
{{- define "n2lab.pkiSecret" -}}
{{- default (printf "%s-n2-pki" (include "n2lab.fullname" .)) .Values.n2Tunnel.pki.existingSecret -}}
{{- end -}}

