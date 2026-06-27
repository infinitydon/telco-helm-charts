{{- define "magma-ebpf.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "magma-ebpf.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "magma-ebpf.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "magma-ebpf.labels" -}}
app.kubernetes.io/name: {{ include "magma-ebpf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{- define "magma-ebpf.selectorLabels" -}}
app.kubernetes.io/name: {{ include "magma-ebpf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "magma-ebpf.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "magma-ebpf.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "magma-ebpf.assertNoLatest" -}}
{{- range $name, $image := .Values.image -}}
{{- if and (kindIs "string" $image) (regexMatch "(:latest)(@sha256:|$)" $image) -}}
{{- fail (printf "image.%s must not use the latest tag" $name) -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "magma-ebpf.rootCASecretName" -}}
{{- if .Values.orc8r.rootCA.existingSecret -}}
{{- .Values.orc8r.rootCA.existingSecret -}}
{{- else -}}
{{- printf "%s-rootca" (include "magma-ebpf.fullname" .) -}}
{{- end -}}
{{- end -}}
