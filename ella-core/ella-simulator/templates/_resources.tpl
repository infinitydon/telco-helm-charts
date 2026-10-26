{{- define "ella.simulator.resources" -}}
{{- $runner := .runner -}}
{{- with .root -}}
{{- $name := printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- $coreHost := tpl .Values.core.host . -}}
{{- if not (contains "." $coreHost) -}}
{{- $coreHost = printf "%s.%s.svc.%s" $coreHost (default .Release.Namespace .Values.core.namespace) .Values.core.clusterDomain -}}
{{- end -}}
{{- $sub := deepCopy .Values.subscriber -}}
{{- if .Values.subscriber.existingSecret -}}{{- $sub = omit $sub "key" "opc" -}}{{- end -}}
apiVersion: v1
kind: ConfigMap
metadata: {name: {{ $name }}}
data:
  supervisor.py: |
    {{- $runner | nindent 4 }}
  settings.json: |
    {{- dict "simulator" .Values.simulator "core" .Values.core "subscriber" $sub "gnb" .Values.gnb "session" .Values.session "backend" .Values.backend "ueCount" .Values.ueCount | toPrettyJson | nindent 4 }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  labels: {app.kubernetes.io/name: {{ .Chart.Name }}, app.kubernetes.io/instance: {{ .Release.Name }}}
spec:
  replicas: 1
  strategy: {type: Recreate}
  selector:
    matchLabels: {app.kubernetes.io/name: {{ .Chart.Name }}, app.kubernetes.io/instance: {{ .Release.Name }}}
  template:
    metadata:
      labels: {app.kubernetes.io/name: {{ .Chart.Name }}, app.kubernetes.io/instance: {{ .Release.Name }}}
      annotations:
        checksum/settings: {{ dict "values" .Values "runner" $runner | toJson | sha256sum }}
    spec:
      automountServiceAccountToken: false
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      nodeSelector:
        {{- toYaml .Values.nodeSelector | nindent 8 }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: simulator
          image: {{ .Values.image | quote }}
          imagePullPolicy: {{ .Values.pullPolicy }}
          command: [python3, /settings/supervisor.py]
          securityContext: {privileged: true}
          env:
            - {name: POD_IP, valueFrom: {fieldRef: {fieldPath: status.podIP}}}
            - name: CORE_HOST
              value: {{ $coreHost | quote }}
            {{- if .Values.subscriber.existingSecret }}
            - {name: SIM_KEY, valueFrom: {secretKeyRef: {name: {{ .Values.subscriber.existingSecret }}, key: key}}}
            - {name: SIM_OPC, valueFrom: {secretKeyRef: {name: {{ .Values.subscriber.existingSecret }}, key: opc}}}
            {{- end }}
          ports: [{name: health, containerPort: 8080}]
          startupProbe: {httpGet: {path: /healthz, port: health}, periodSeconds: 3, failureThreshold: 80}
          readinessProbe: {httpGet: {path: /healthz, port: health}, periodSeconds: 3}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          volumeMounts:
            - {name: settings, mountPath: /settings, readOnly: true}
            - {name: run, mountPath: /run/simulator}
            - {name: tun, mountPath: /dev/net/tun}
      volumes:
        - {name: settings, configMap: {name: {{ $name }}}}
        - {name: run, emptyDir: {medium: Memory}}
        - {name: tun, hostPath: {path: /dev/net/tun, type: CharDevice}}
---
apiVersion: v1
kind: Service
metadata: {name: {{ $name }}}
spec:
  type: ClusterIP
  selector: {app.kubernetes.io/name: {{ .Chart.Name }}, app.kubernetes.io/instance: {{ .Release.Name }}}
  ports: [{name: health, port: 8080, targetPort: health}]
---
apiVersion: v1
kind: Pod
metadata:
  name: {{ $name }}-test
  annotations:
    helm.sh/hook: test
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  nodeSelector:
    {{- toYaml .Values.nodeSelector | nindent 4 }}
  {{- with .Values.imagePullSecrets }}
  imagePullSecrets:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  containers:
    - name: health
      image: {{ .Values.image | quote }}
      command: [python3, -c]
      args:
        - "import json,urllib.request; r=json.load(urllib.request.urlopen('http://{{ $name }}:8080/healthz',timeout=10)); assert r['ready'] and r['ueIPv4']; print(r)"
{{- end -}}
{{- end -}}
