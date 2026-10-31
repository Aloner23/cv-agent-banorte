#!/usr/bin/env python3
"""Genera artefactos revisables; --apply los instala en el proyecto seleccionado."""
import argparse
import json
from pathlib import Path
import subprocess


def configs(service):
    logs = f'resource.type="cloud_run_revision" resource.labels.service_name="{service}"'
    metric_filter = f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service}"'
    metrics = []
    for name, field, unit, bounds in [
        ('latency_ms', 'ms', 'ms', [100, 250, 500, 1000, 2000, 5000, 10000, 30000, 60000, 120000]),
        ('ttft_ms', 'ttft_ms', 'ms', [100, 250, 500, 1000, 2000, 5000, 10000, 30000, 60000]),
        ('input_tokens', 'input_tokens', '1', [100, 500, 1000, 2000, 4000, 8000, 16000, 32000]),
        ('output_tokens', 'output_tokens', '1', [10, 50, 100, 250, 500, 1000, 2000]),
    ]:
        metrics.append({'name': f'cv_agent_{name}', 'description': f'CV agent: {field} por respuesta',
            'filter': f'{logs} jsonPayload.message="response" jsonPayload.{field}>=0',
            'metricDescriptor': {'metricKind': 'DELTA', 'valueType': 'DISTRIBUTION', 'unit': unit},
            'valueExtractor': f'EXTRACT(jsonPayload.{field})',
            'bucketOptions': {'explicitBuckets': {'bounds': bounds}}})
    metrics.append({'name': 'cv_agent_failures', 'description': 'Fallos terminales, incluidos los enviados por SSE con HTTP 200',
        'filter': f'{logs} jsonPayload.message="response_failed"',
        'metricDescriptor': {'metricKind': 'DELTA', 'valueType': 'INT64', 'unit': '1'}})
    charts = [
        ('Solicitudes / segundo', 'run.googleapis.com/request_count', 'ALIGN_RATE', 'REDUCE_SUM'),
        ('Latencia del agente p95 (ms)', 'logging.googleapis.com/user/cv_agent_latency_ms', 'ALIGN_DELTA', 'REDUCE_PERCENTILE_95'),
        ('Primer texto p95 (ms)', 'logging.googleapis.com/user/cv_agent_ttft_ms', 'ALIGN_DELTA', 'REDUCE_PERCENTILE_95'),
        ('Fallos terminales / minuto (JSON y SSE)', 'logging.googleapis.com/user/cv_agent_failures', 'ALIGN_SUM', 'REDUCE_SUM'),
        ('Tokens de entrada p95 / respuesta', 'logging.googleapis.com/user/cv_agent_input_tokens', 'ALIGN_DELTA', 'REDUCE_PERCENTILE_95'),
        ('Tokens de salida p95 / respuesta', 'logging.googleapis.com/user/cv_agent_output_tokens', 'ALIGN_DELTA', 'REDUCE_PERCENTILE_95'),
        ('Instancias activas', 'run.googleapis.com/container/instance_count', 'ALIGN_MAX', 'REDUCE_SUM'),
    ]
    tiles=[]
    for i, (title, metric, align, reduce) in enumerate(charts):
        tiles.append({'xPos': (i % 2)*6, 'yPos': (i//2)*4, 'width': 6, 'height': 4,
            'widget': {'title': title, 'xyChart': {'dataSets': [{'timeSeriesQuery': {'timeSeriesFilter': {
                'filter': f'{metric_filter} AND metric.type="{metric}"',
                'aggregation': {'alignmentPeriod': '60s', 'perSeriesAligner': align, 'crossSeriesReducer': reduce}}},
                'plotType': 'LINE'}]}}})
    dashboard={'displayName': f'{service} · Operación IA', 'mosaicLayout': {'columns':12,'tiles':tiles}}
    alert={'displayName': f'{service} · Fallos del agente', 'combiner': 'OR', 'enabled': True,
        'documentation': {'content': 'Tres o más fallos terminales en cinco minutos. Revisar response_failed, error_code y request_id en Cloud Logging. Un stream puede fallar con HTTP 200. No volver a intentar automáticamente errores de cuota.', 'mimeType':'text/markdown'},
        'conditions': [{'displayName': 'Fallos terminales >= 3 en 5 min', 'conditionThreshold': {
            'filter': f'{metric_filter} AND metric.type="logging.googleapis.com/user/cv_agent_failures"',
            'comparison': 'COMPARISON_GT', 'thresholdValue': 2, 'duration':'0s',
            'aggregations':[{'alignmentPeriod':'300s','perSeriesAligner':'ALIGN_SUM','crossSeriesReducer':'REDUCE_SUM'}],
            'trigger':{'count':1}}}]}
    return metrics,dashboard,alert


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--service',default='carlos-cv-agent')
    p.add_argument('--output',default='tmp/observability');p.add_argument('--channel');p.add_argument('--apply',action='store_true');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    metrics,dashboard,alert=configs(a.service)
    if a.channel: alert['notificationChannels']=[a.channel]
    def save(name, data):
        path=out/(name+'.json');path.write_text(json.dumps(data,ensure_ascii=False,indent=2));return str(path)
    for metric in metrics: save(metric['name'],metric)
    save('dashboard',dashboard);save('alert',alert)
    if not a.apply:
        print(f'Configuración generada en {out}; no se crearon recursos.');return
    def run(*args, read=False):
        result=subprocess.run(['gcloud',*args,'--project',a.project,'--quiet'],check=True,text=True,capture_output=True)
        return json.loads(result.stdout) if read else None
    existing={m['name'] for m in run('logging','metrics','list','--format=json',read=True)}
    for metric in metrics:
        run('logging','metrics','update' if metric['name'] in existing else 'create',metric['name'],f"--config-from-file={out / (metric['name']+'.json')}")
    matches=[d for d in run('monitoring','dashboards','list','--format=json',read=True) if d.get('displayName')==dashboard['displayName']]
    if len(matches)>1: raise RuntimeError('Hay paneles duplicados; elegir explícitamente antes de actualizar.')
    if matches:
        dashboard.update({k:matches[0][k] for k in ('name','etag') if k in matches[0]})
        run('monitoring','dashboards','update',matches[0]['name'],f"--config-from-file={save('dashboard',dashboard)}")
    else: run('monitoring','dashboards','create',f"--config-from-file={out/'dashboard.json'}")
    matches=[v for v in run('monitoring','policies','list','--format=json',read=True) if v.get('displayName')==alert['displayName']]
    if len(matches)>1: raise RuntimeError('Hay alertas duplicadas; elegir explícitamente antes de actualizar.')
    if matches:
        if not a.channel: alert['notificationChannels']=matches[0].get('notificationChannels',[])
        alert['name']=matches[0]['name']
        run('monitoring','policies','update',matches[0]['name'],f"--policy-from-file={save('alert',alert)}")
    else: run('monitoring','policies','create',f"--policy-from-file={out/'alert.json'}")
    print('Panel, métricas y política instalados. Sin canal, los incidentes se ven sólo en la consola.')

if __name__=='__main__': main()
