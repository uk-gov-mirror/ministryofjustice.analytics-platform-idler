"""
Checks all RStudio deployments and idles those matching criteria
"""

from datetime import datetime, timezone
import logging

from kubernetes import client, config


IDLED = 'mojanalytics.xyz/idled'
IDLED_AT = 'mojanalytics.xyz/idled-at'
UNIDLER = 'unidler'


log = logging.getLogger(__name__)


def idle_deployments():
    for deployment in eligible_deployments():
        idle(deployment)


def eligible_deployments():
    deployments = client.AppsV1beta1Api().list_deployment_for_all_namespaces(
        label_selector=f'!{IDLED},app=rstudio')
    return filter(eligible, deployments.items)


def eligible(deployment):
    return True


def idle(deployment):
    mark_idled(deployment)
    redirect_to_unidler(deployment)
    zero_replicas(deployment)
    write_changes(deployment)
    log.debug(
        f'{deployment.metadata.name} '
        f'in namespace {deployment.metadata.namespace} '
        f'idled')


def mark_idled(deployment):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    deployment.metadata.labels[IDLED] = 'true'
    deployment.metadata.annotations[IDLED_AT] = (
        f'{timestamp},{deployment.spec.replicas}')


def redirect_to_unidler(deployment):
    ingress = get_deployment_ingress(deployment)
    set_unidler_backend(ingress)
    write_ingress_changes(ingress)


def get_deployment_ingress(deployment):
    return client.ExtensionsV1beta1Api().read_namespaced_ingress(
        deployment.metadata.name,
        deployment.metadata.namespace)


def set_unidler_backend(ingress):
    ingress.spec.rules[0].http.paths[0].backend.serviceName = UNIDLER


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


if __name__ == '__main__':
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()

    idle_deployments()
