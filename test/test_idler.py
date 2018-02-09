from datetime import datetime, timezone
from unittest import mock

import pytest

import idler
from idler import IDLED, IDLED_AT, UNIDLER


@pytest.yield_fixture
def current_time():
    dt = mock.MagicMock()
    now = datetime(2018, 2, 7, 11, 44, 20, tzinfo=timezone.utc)
    dt.now.return_value = now
    with mock.patch('idler.datetime', dt):
        yield now


@pytest.fixture
def deployment():
    deployment = mock.MagicMock()
    deployment.metadata.annotations = {}
    deployment.metadata.labels = {'app': 'rstudio'}
    deployment.spec.replicas = expected_replicas = 2
    return deployment


@pytest.yield_fixture
def api(deployment):
    api = mock.MagicMock()
    api.list_deployment_for_all_namespaces.return_value.items = [
        deployment,
    ]
    with mock.patch('idler.api', api):
        yield api


def test_eligible(deployment):
    assert idler.eligible(deployment)


def test_eligible_deployments(api):
    deployments = idler.eligible_deployments()
    api.list_deployment_for_all_namespaces.assert_called_with(
        label_selector=f'!{IDLED},app=rstudio')
    assert len(list(deployments)) > 0


def test_mark_idled(deployment, current_time):
    expected_replicas = deployment.spec.replicas

    idler.mark_idled(deployment)

    assert IDLED in deployment.metadata.labels
    assert IDLED_AT in deployment.metadata.annotations
    timestamp, replicas = deployment.metadata.annotations[IDLED_AT].split(',')
    assert int(replicas) == expected_replicas
    assert timestamp == current_time.isoformat(timespec='seconds')


def test_get_deployment_ingress(api, deployment):
    idler.get_deployment_ingress(deployment)

    api.read_namespaced_ingress.assert_called_with(
        deployment.metadata.name,
        deployment.metadata.namespace)


def test_set_unidler_backend():
    ingress = mock.MagicMock()
    ingress.spec.rules = [mock.MagicMock()]
    ingress.spec.rules[0].http.paths = [mock.MagicMock()]

    idler.set_unidler_backend(ingress)

    assert ingress.spec.rules[0].http.paths[0].backend.serviceName == UNIDLER


def test_write_ingress_changes(api):
    ingress = mock.MagicMock()

    idler.write_ingress_changes(ingress)

    api.patch_namespaced_ingress.assert_called_with(
        ingress.metadata.name,
        ingress.metadata.namespace,
        ingress)


def test_zero_replicas(deployment):
    idler.zero_replicas(deployment)

    assert deployment.spec.replicas == 0


def test_write_changes(api, deployment):
    idler.write_changes(deployment)

    api.patch_namespaced_deployment.assert_called_with(
        deployment.metadata.name,
        deployment.metadata.namespace,
        deployment
    )
