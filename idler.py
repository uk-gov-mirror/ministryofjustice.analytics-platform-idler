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


IDLED = 'mojanalytics.xyz/idled'
IDLED_AT = 'mojanalytics.xyz/idled-at'
INGRESS_CLASS = 'kubernetes.io/ingress.class'
UNIDLER = 'unidler'


log = logging.getLogger(__name__)
ingress_lookup = {}


def idle_deployments():
    build_ingress_lookup()

    with ingress(UNIDLER, 'default') as unidler:
        for deployment in eligible_deployments():
            idle(deployment, unidler)


@contextlib.contextmanager
def ingress(name, namespace):
    ingress = ingress_lookup[(name, namespace)]
    yield ingress
    write_ingress_changes(ingress)


def build_ingress_lookup():
    ingresses = client.ExtensionsV1beta1Api().list_ingress_for_all_namespaces()
    for i in ingresses.items:
        ingress_lookup[(i.metadata.name, i.metadata.namespace)] = i


def eligible_deployments():
    label_selector = os.environ.get('LABEL_SELECTOR', 'app=rstudio')
    if label_selector:
        label_selector = ',' + label_selector

    return client.AppsV1beta1Api().list_deployment_for_all_namespaces(
        label_selector=f'!{IDLED}{label_selector}').items


def idle(deployment, unidler):
    mark_idled(deployment)
    redirect_to_unidler(deployment, unidler)
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


def redirect_to_unidler(deployment, unidler):
    name = deployment.metadata.name
    namespace = deployment.metadata.namespace

    with ingress(name, namespace) as ing:
        disable_ingress(ing)
        add_host_rule(unidler, ing)


def disable_ingress(ingress):
    ingress.metadata.annotations[INGRESS_CLASS] = 'disabled'


def add_host_rule(unidler, ingress):
    unidler.spec.rules.append(
        V1beta1IngressRule(
            # XXX assumption: ingress has rules and first one is relevant
            host=ingress.spec.rules[0].host,
            http=V1beta1HTTPIngressRuleValue(
                paths=[
                    V1beta1HTTPIngressPath(
                        backend=V1beta1IngressBackend(
                            service_name=UNIDLER,
                            service_port=80))])))


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
