{{- define "ella-core.name" -}}
ella-core
{{- end }}

{{- define "ella-core.serviceName" -}}
ella-core
{{- end }}

{{- define "ella-core.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ella-core.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "ella-core.namespace" -}}
{{ .Release.Namespace }}
{{- end }}

{{- /*
  Build a peer FQDN for a given pod index.
  Usage: {{ include "ella-core.peer" (dict "root" . "idx" 2) }}
  Produces: ella-core-2.ella-core.<ns>.svc.cluster.local:<raftPort>
*/ -}}
{{- define "ella-core.peer" -}}
{{- $svc := include "ella-core.serviceName" .root -}}
{{- $ns := include "ella-core.namespace" .root -}}
{{- $raftPort := .root.Values.raft.port | toString -}}
{{ $svc }}-{{ .idx }}.{{ $svc }}.{{ $ns }}.svc.cluster.local:{{ $raftPort }}
{{- end }}
