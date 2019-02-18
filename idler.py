"""
Checks all RStudio deployments and idles those matching a kubernetes label
selector.
The label selector can be overridden by setting the LABEL_SELECTOR environment
variable.
See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
for label selector syntax.
"""

from datetime import datetime, timezone
import json
import logging
import os

from kubernetes import client, config

# provides swagger definitions for metrics api
import metrics_api


LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)


ACTIVE_INSTANCE_CPU_PERCENTAGE = 90
try:
    ACTIVE_INSTANCE_CPU_PERCENTAGE = int(os.environ.get(
        'RSTUDIO_ACTIVITY_CPU_THRESHOLD', 90))
    log.debug(
        f'RSTUDIO_ACTIVITY_CPU_THRESHOLD={ACTIVE_INSTANCE_CPU_PERCENTAGE}%')
except ValueError:
    log.warning(
        'Invalid value for RSTUDIO_ACTIVITY_CPU_THRESHOLD, using default')

IDLED = 'mojanalytics.xyz/idled'
IDLED_AT = 'mojanalytics.xyz/idled-at'
SERVICE_TYPE_EXTERNAL_NAME = "ExternalName"
UNIDLER_SERVICE_HOST = "unidler.default.svc.cluster.local"


metrics_lookup = {}
pods_lookup = {}


def idle_deployments():
    build_lookups()

    for deployment in eligible_deployments():
        if should_idle(deployment):
            idle(deployment)


def get_key(pod_or_deployment):
    return (
        pod_or_deployment.metadata.labels['app'],
        pod_or_deployment.metadata.namespace,
    )


def build_metrics_lookup():
    metrics = client.MetricsV1beta1Api().list_pod_metrics_for_all_namespaces(
        label_selector=f'!{IDLED}{label_selector()}')

    for pod_metrics in metrics.items:
        pod_name = pod_metrics.metadata.name
        namespace = pod_metrics.metadata.namespace
        pod = pods_lookup[(pod_name, namespace)]
        app_name = pod.metadata.labels['app']

        metrics_lookup[(app_name, namespace)] = pod_metrics


def build_pods_lookup():
    pods = client.CoreV1Api().list_pod_for_all_namespaces(
        label_selector=f'!{IDLED}{label_selector()}')
    for pod in pods.items:
        pods_lookup[(pod.metadata.name, pod.metadata.namespace)] = pod


def build_lookups():
    build_pods_lookup()
    build_metrics_lookup()


def eligible_deployments():
    return client.AppsV1beta1Api().list_deployment_for_all_namespaces(
        label_selector=f'!{IDLED}{label_selector()}').items


def label_selector():
    label_selector = os.environ.get('LABEL_SELECTOR', 'app=rstudio')
    log.debug(f'LABEL_SELECTOR="{label_selector}"')
    if label_selector:
        label_selector = ',' + label_selector
    return label_selector


def should_idle(deployment):
    usage = 0
    key = get_key(deployment)

    try:
        usage = avg_cpu_percent(deployment)
    except ValueError as ve:
        log.exception(f'{key}: Using unknown unit of CPU: {ve}', exc_info=True)

    log.debug(f'{key}: Using {usage}% of CPU')

    if usage > ACTIVE_INSTANCE_CPU_PERCENTAGE:
        log.info(f'{key}: Not idling as using {usage}% of CPU')
        return False

    return True


def core_val_with_unit_to_int(core_val_with_unit: str):
    # millicpus have the 'm' suffix
    if core_val_with_unit.endswith('m'):
        return int(core_val_with_unit.rstrip('m'), 10)
    elif core_val_with_unit.endswith('n'):
        # nanocpus have the 'n' suffix
        return int(core_val_with_unit.rstrip('n'), 10) / 1000000
    elif core_val_with_unit.endswith('u'):
        # microcpus (μ)
        return int(core_val_with_unit.rstrip('u'), 10) / 1000
    else:
        # if the result is 0 then there is no suffix
        return int(core_val_with_unit, 10)


def avg_cpu_percent(deployment):
    key = get_key(deployment)
    try:
        metrics = metrics_lookup[key]
    except KeyError as e:
        log.warning(f'{key}: Metrics not found, pod may be unhealthy.')
        return 0

    usage = 0
    for container in metrics.containers:
        usage += core_val_with_unit_to_int(container.usage['cpu'])

    total = 0
    for container in deployment.spec.template.spec.containers:
        total += core_val_with_unit_to_int(container.resources.limits['cpu'])

    return usage / total * 100.0


def idle(deployment):
    mark_idled(deployment)
    svc = Service(deployment.metadata.name, deployment.metadata.namespace)
    svc.redirect_to_unidler()
    zero_replicas(deployment)
    write_changes(deployment)

    log.debug(f'{get_key(deployment)}: Idled')


def mark_idled(deployment):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    deployment.metadata.labels[IDLED] = 'true'
    deployment.metadata.annotations[IDLED_AT] = (
        f'{timestamp},{deployment.spec.replicas}')


class Service(object):

    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace
        self.service = client.CoreV1Api().read_namespaced_service(
            name, namespace)

    def patch(self, *patch):
        client.CoreV1Api().patch_namespaced_service(
            name=self.name,
            namespace=self.namespace,
            body=list(patch))

    def redirect_to_unidler(self):
        self.patch(
            {
                "op": "replace",
                "path": "/spec/type",
                "value": SERVICE_TYPE_EXTERNAL_NAME},
            {
                "op": "add",
                "path": "/spec/externalName",
                "value": UNIDLER_SERVICE_HOST},
            {
                "op": "replace",
                "path": "/spec/ports",
                "value": [
                    {
                        "name": "http",
                        "port": 80,
                        "protocol": "TCP",
                        "targetPort": 80
                    }
                ]},
            {
                "op": "remove",
                "path": "/spec/selector"},
            {
                "op": "remove",
                "path": "/spec/clusterIP"})


def zero_replicas(deployment):
    deployment.spec.replicas = 0


def write_changes(deployment):
    client.AppsV1beta1Api().patch_namespaced_deployment(
        deployment.metadata.name,
        deployment.metadata.namespace,
        deployment)


def load_kube_config():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        # monkeypatch config loader to handle OIDC
        import k8s_oidc
        config.load_kube_config()


if __name__ == '__main__':
    load_kube_config()
    idle_deployments()
