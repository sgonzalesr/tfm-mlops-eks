{{- define "inference-service.name" -}}
inference
{{- end -}}

{{- define "inference-service.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "inference-service.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "inference-service.labels" -}}
app.kubernetes.io/name: {{ include "inference-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
