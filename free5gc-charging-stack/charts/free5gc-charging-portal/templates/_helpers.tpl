{{- define "free5gc-charging-portal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "free5gc-charging-portal.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "free5gc-charging-portal.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
app.kubernetes.io/name: {{ include "free5gc-charging-portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "free5gc-charging-portal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "free5gc-charging-portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "free5gc-charging-portal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "free5gc-charging-portal.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "free5gc-charging-portal.secretName" -}}
{{- default (printf "%s-auth" (include "free5gc-charging-portal.fullname" .)) .Values.auth.existingSecret -}}
{{- end -}}

{{- define "free5gc-charging-portal.validateImages" -}}
{{- if or (eq .Values.image.tag "latest") (regexMatch "(:latest$|^latest$)" .Values.image.tag) -}}
{{- fail "image.tag must not use latest" -}}
{{- end -}}
{{- end -}}
