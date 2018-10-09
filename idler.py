"""
Checks all RStudio deployments and idles those matching a kubernetes label
selector.
The label selector can be overridden by setting the LABEL_SELECTOR environment
variable.
See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
for label selector syntax.
"""

import contextlib
from datetime import datetime, timezone
import logging
import os

from kubernetes import client, config
from kubernetes.client.models import (
    V1beta1HTTPIngressPath,
    V1beta1HTTPIngressRuleValue,
    V1beta1IngressBackend,
    V1beta1IngressRule,
)

import metrics_api


LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)


ACTIVE_INSTANCE_CPU_PERCENTAGE = 90
try:
    ACTIVE_INSTANCE_CPU_PERCENTAGE = int(os.environ.get(
        'RSTUDIO_ACTIVITY_CPU_THRESHOLD', 90))
    log.debug(f'RSTUDIO_ACTIVITY_CPU_THRESHOLD={ACTIVE_INSTANCE_CPU_PERCENTAGE}%')
except ValueError:
    log.warning(
        'Invalid value for RSTUDIO_ACTIVITY_CPU_THRESHOLD, using default')

IDLED = 'mojanalytics.xyz/idled'
IDLED_AT = 'mojanalytics.xyz/idled-at'
INGRESS_CLASS = 'kubernetes.io/ingress.class'
UNIDLER = 'unidler'


ingress_lookup = {}
metrics_lookup = {}
pods_lookup = {}


def idle_deployments():
    build_lookups()

    with ingress(UNIDLER, 'default') as unidler:
        for deployment in eligible_deployments():
            if should_idle(deployment):
                idle(deployment, unidler)

def get_key(pod_or_deployment):
    return (
        pod_or_deployment.metadata.labels['app'],
        pod_or_deployment.metadata.namespace,
    )


@contextlib.contextmanager
def ingress(name, namespace):
    ingress = ingress_lookup[(name, namespace)]
    yield ingress
    write_ingress_changes(ingress)


def build_ingress_lookup():
    ingresses = client.ExtensionsV1beta1Api().list_ingress_for_all_namespaces()
    for i in ingresses.items:
        ingress_lookup[(i.metadata.name, i.metadata.namespace)] = i


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
    pods = client.CoreV1Api().list_pod_for_all_namespaces(label_selector=f'!{IDLED}{label_selector()}')
    for pod in pods.items:
        pods_lookup[(pod.metadata.name, pod.metadata.namespace)] = pod


def build_lookups():
    build_pods_lookup()
    build_metrics_lookup()
    build_ingress_lookup()


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


def idle(deployment, unidler):
    mark_idled(deployment)
    redirect_to_unidler(deployment, unidler)
    zero_replicas(deployment)
    write_changes(deployment)

    log.debug(f'{get_key(deployment)}: Idled')


def mark_idled(deployment):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    deployment.metadata.labels[IDLED] = 'true'
    deployment.metadata.annotations[IDLED_AT] = (
        f'{timestamp},{deployment.spec.replicas}')


def redirect_to_unidler(deployment, unidler):
    name = deployment.metadata.name
    namespace = deployment.metadata.namespace

    with ingress(name, namespace) as ing:
        disable_ingress(ing)
        add_host_rule(unidler, ing)


def disable_ingress(ingress):
    ingress.metadata.annotations[INGRESS_CLASS] = 'disabled'


def add_host_rule(unidler, ingress):
    # XXX assumption: ingress has rules and first one is relevant
    hostname = ingress.spec.rules[0].host
    unidler.spec.rules.append(
        V1beta1IngressRule(
            host=hostname,
            http=V1beta1HTTPIngressRuleValue(
                paths=[
                    V1beta1HTTPIngressPath(
                        backend=V1beta1IngressBackend(
                            service_name=UNIDLER,
                            service_port=80))])))
    # ensure the host is listed in tls hosts
    if hostname not in unidler.spec.tls[0].hosts:
        unidler.spec.tls[0].hosts.append(hostname)


def write_ingress_changes(ingress):
    client.ExtensionsV1beta1Api().patch_namespaced_ingress(
        ingress.metadata.name,
        ingress.metadata.namespace,
        ingress)


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
    except:
        import k8s_oidc
        config.load_kube_config()


if __name__ == '__main__':
    load_kube_config()
    idle_deployments()
