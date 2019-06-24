"""
Idles applications to save resources.

Idling is performed by scaling down a deployment to zero replicas (no pods
running).

Only apps with the given label (`LABEL_SELECTOR`) and that are not using more
than the given CPU threshold (`CPU_ACTIVITY_THRESHOLD`) will be idled.

See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
for label selector syntax.
"""

from datetime import datetime, timezone
import json
import logging
import os
from sys import exit

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


CPU_ACTIVITY_THRESHOLD = 90
try:
    CPU_ACTIVITY_THRESHOLD = int(os.environ.get(
        'CPU_ACTIVITY_THRESHOLD', CPU_ACTIVITY_THRESHOLD))
    log.debug(
        f'CPU_ACTIVITY_THRESHOLD={CPU_ACTIVITY_THRESHOLD}%')
except ValueError:
    log.warning(
        f'Invalid value for CPU_ACTIVITY_THRESHOLD, using default ({CPU_ACTIVITY_THRESHOLD}%)')

LABEL_SELECTOR = os.environ.get('LABEL_SELECTOR', 'mojanalytics.xyz/idleable=true').strip()
log.debug(f'LABEL_SELECTOR="{LABEL_SELECTOR}"')

IDLED = 'mojanalytics.xyz/idled'
IDLED_AT = 'mojanalytics.xyz/idled-at'
REPLICAS_WHEN_UNIDLED = 'mojanalytics.xyz/replicas-when-unidled'
SERVICE_TYPE_EXTERNAL_NAME = "ExternalName"
UNIDLER_SERVICE_HOST = "unidler.default.svc.cluster.local"


metrics_lookup = {}
pods_lookup = {}


def idle_deployments():
    build_lookups()

    failed = []
    for deployment in eligible_deployments():
        try:
            if should_idle(deployment):
                idle(deployment)
        except Exception as e:
            deploy_id = f"({deployment.metadata.namespace}, {deployment.metadata.name})"
            log.error(f"Failed to idle {deploy_id} deployment: {e}")
            failed.append(deploy_id)

    if failed:
        failed_deployments = "\n".join(failed)
        log.error(f"Failed to idle following deployments:\n {failed_deployments}")
        exit(1)


def get_key(pod_or_deployment):
    return (
        pod_or_deployment.metadata.labels['app'],
        pod_or_deployment.metadata.namespace,
    )


def build_metrics_lookup():
    metrics = client.MetricsV1beta1Api().list_pod_metrics_for_all_namespaces(
        label_selector=LABEL_SELECTOR).items
    log.debug(f"{len(metrics)} metrics found matching the '{LABEL_SELECTOR}' label selector.")

    for pod_metrics in metrics:
        pod_name = pod_metrics.metadata.name
        namespace = pod_metrics.metadata.namespace
        pod = pods_lookup[(pod_name, namespace)]
        app_name = pod.metadata.labels['app']

        metrics_lookup[(app_name, namespace)] = pod_metrics


def build_pods_lookup():
    pods = client.CoreV1Api().list_pod_for_all_namespaces(
        label_selector=LABEL_SELECTOR).items
    log.debug(f"{len(pods)} pods found matching the '{LABEL_SELECTOR}' label selector.")

    for pod in pods:
        pods_lookup[(pod.metadata.name, pod.metadata.namespace)] = pod


def build_lookups():
    build_pods_lookup()
    build_metrics_lookup()


def eligible_deployments():
    selector = f"!{IDLED}"
    if LABEL_SELECTOR:
        selector = f"{selector},{LABEL_SELECTOR}"

    deployments = client.AppsV1beta1Api().list_deployment_for_all_namespaces(
        label_selector=selector).items
    log.debug(f"{len(deployments)} deployments found matching the '{selector}' label selector.")

    return deployments


def should_idle(deployment):
    usage = 0
    key = get_key(deployment)

    try:
        usage = avg_cpu_percent(deployment)
    except ValueError as ve:
        log.exception(f'{key}: Using unknown unit of CPU: {ve}', exc_info=True)

    log.debug(f'{key}: Using {usage}% of CPU')

    if usage > CPU_ACTIVITY_THRESHOLD:
        log.info(f"{key}: will not be idled as it's using {usage}% of CPU.")
        return False

    log.debug(f"{key}: will be idled.")
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
        log.warning(f'{key}: Metrics not found, pod may be unhealthy. Assuming 0% CPU usage.')
        return 0

    usage = 0
    for container in metrics.containers:
        usage += core_val_with_unit_to_int(container.usage['cpu'])

    total = 0
    for container in deployment.spec.template.spec.containers:
        total += core_val_with_unit_to_int(container.resources.limits['cpu'])

    return usage / total * 100.0


def idle(deployment):
    key = get_key(deployment)

    app = App(deployment.metadata.name, deployment.metadata.namespace)

    app.redirect_to_unidler()
    log.debug(f'{key}: Service pointed to unidler (set ServiceType to ExternalName, etc).')

    app.scale_to_zero(replicas_when_unidled=deployment.spec.replicas)
    log.debug(f'{key}: Deployment idled: Set replicas to 0, added labels and annotations.')


class App(object):

    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    def redirect_to_unidler(self):
        patch = {
            "spec": {
                "selector": None, # remove
                "clusterIP": None, # remove
                "type": SERVICE_TYPE_EXTERNAL_NAME,
                "externalName": UNIDLER_SERVICE_HOST,
                "ports": [
                    {
                        "name": "http",
                        "port": 80,
                        "protocol": "TCP",
                        "targetPort": 80
                    }
                ]
            }
        }

        client.CoreV1Api().patch_namespaced_service(
            name=self.name,
            namespace=self.namespace,
            body=patch,
        )

    def scale_to_zero(self, replicas_when_unidled=1):
        idled_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

        patch = {
            "spec": {
                "replicas": 0
            },
            "metadata": {
                "labels": {
                    IDLED: "true",
                },
                "annotations": {
                    IDLED_AT: idled_at,
                    REPLICAS_WHEN_UNIDLED: str(replicas_when_unidled),
                },
            },
        }

        client.AppsV1beta1Api().patch_namespaced_deployment(
            self.name,
            self.namespace,
            body=patch,
        )


def load_kube_config():
    try:
        config.load_incluster_config()
        log.debug("Kubernetes configuration loaded from within the cluster.")
    except config.ConfigException:
        # monkeypatch config loader to handle OIDC
        import k8s_oidc
        config.load_kube_config()
        log.debug("Kubernetes configuration loaded from kube_config file.")


if __name__ == '__main__':
    load_kube_config()
    idle_deployments()
