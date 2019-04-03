from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis.strategies import integers, text, composite

import idler
from idler import (
    IDLED,
    IDLED_AT,
    REPLICAS_WHEN_UNIDLED,
    SERVICE_TYPE_EXTERNAL_NAME,
    UNIDLER_SERVICE_HOST,
)


@composite
def cpu_usage(draw):
    n = draw(integers(min_value=1))
    u = draw(text(alphabet='mnu', max_size=1, min_size=1))
    return f'{n}{u}'


@given(cpu_usage())
@settings(max_examples=1500)
def test_parse_cpuusage(cpu: str):
    out = 0
    if cpu.endswith('n'):
        out = int(cpu.rstrip('n')) / 1000000
    elif cpu.endswith('m'):
        out = int(cpu.rstrip('m'))
    elif cpu.endswith('u'):
        out = int(cpu.rstrip('u')) / 1000
    assert idler.core_val_with_unit_to_int(cpu) == out


@pytest.yield_fixture
def current_time():
    dt = MagicMock()
    now = datetime(2018, 2, 7, 11, 44, 20, tzinfo=timezone.utc)
    dt.now.return_value = now
    with patch('idler.datetime', dt):
        yield now


def mock_container(cpu_limit):
    container = MagicMock()
    container.resources.limits = {'cpu': cpu_limit}

    return container


@pytest.fixture
def deployment():
    deployment = MagicMock()
    deployment.metadata.annotations = {}
    deployment.metadata.labels = {
        'app': 'rstudio',
        'mojanalytics.xyz/idleable': 'true',
    }
    deployment.metadata.namespace = 'user-alice'
    deployment.spec.replicas = 2
    deployment.spec.template.spec.containers = [
        mock_container(cpu_limit='100m'),
        mock_container(cpu_limit='1500m'),
    ]
    return deployment


@pytest.fixture
def pod():
    pod = MagicMock()
    pod.metadata.name = 'rstudio-whatever-1234-abcde'
    pod.metadata.labels = {'app': 'rstudio'}
    pod.metadata.namespace = 'user-alice'
    return pod


@pytest.yield_fixture
def client(deployment, pod):
    client = MagicMock()
    apps_api = client.AppsV1beta1Api.return_value
    apps_api.list_deployment_for_all_namespaces.return_value.items = [
        deployment,
    ]

    core_api = client.CoreV1Api.return_value
    core_api.list_pod_for_all_namespaces.return_value.items = [
        pod,
    ]

    with patch('idler.client', client):
        yield client


@pytest.yield_fixture
def env():
    env = {}
    with patch('idler.os') as mock_os:
        mock_os.environ = env
        yield env


@pytest.fixture
def unidler():
    unidler = MagicMock()
    unidler.spec.rules = [
        MagicMock(),
    ]
    unidler.spec.tls = [MagicMock()]
    unidler.spec.tls[0].hosts = []
    return unidler


def mock_podmetric(cpu_usage=None):
    if cpu_usage is None:
        cpu_usage = ['0']
    metric = MagicMock(name='PodMetrics')
    metric.containers = []
    for usage in cpu_usage:
        container = MagicMock(name='Container')
        container.usage = {'cpu': usage}
        metric.containers.append(container)
    return metric


@pytest.yield_fixture
def metrics(deployment):
    metric = mock_podmetric()
    cache = {
        (deployment.metadata.labels['app'], deployment.metadata.namespace):
            metric,
    }
    with patch('idler.metrics_lookup', cache):
        yield cache


@pytest.yield_fixture
def pods_lookup(pod):
    cache = {
        (pod.metadata.labels['app'], pod.metadata.namespace): pod,
    }
    with patch('idler.pods_lookup', cache):
        yield cache


def test_idle_deployments(client, deployment, env, metrics):
    core_api = client.CoreV1Api.return_value
    apps_api = client.AppsV1beta1Api.return_value

    idler.idle_deployments()

    apps_api.patch_namespaced_deployment.assert_called_with(
        deployment.metadata.name,
        deployment.metadata.namespace,
        deployment)

    core_api.read_namespaced_service.assert_called_with(
        deployment.metadata.name,
        deployment.metadata.namespace)

    core_api.patch_namespaced_service.assert_called_with(
        name=deployment.metadata.name,
        namespace=deployment.metadata.namespace,
        body=[
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
                "path": "/spec/clusterIP"}])


def test_eligible_deployments(client, env):
    deployments = idler.eligible_deployments()
    api = client.AppsV1beta1Api.return_value
    api.list_deployment_for_all_namespaces.assert_called_with(
        label_selector=f'!{IDLED},mojanalytics.xyz/idleable=true')
    assert len(list(deployments)) > 0


@pytest.mark.parametrize('label_selector, expected', [
    ('foo', f'!{IDLED},foo'),
    ('foo=bar', f'!{IDLED},foo=bar'),
    ('!foo', f'!{IDLED},!foo'),
    ('', f'!{IDLED}'),
])
def test_label_selector(client, env, label_selector, expected):
    with patch('idler.LABEL_SELECTOR', label_selector):
        idler.eligible_deployments()

        api = client.AppsV1beta1Api.return_value
        api.list_deployment_for_all_namespaces.assert_called_with(
            label_selector=expected)


def test_should_idle(deployment, env, metrics):
    assert idler.should_idle(deployment)


def test_should_not_idle(deployment, env):
    with patch('idler.avg_cpu_percent') as cpu:
        cpu.return_value = 100
        assert not idler.should_idle(deployment)


@pytest.mark.parametrize('cpu_usage, expected', [
    (['0'], 0),
    (['0', '0'], 0),
    (['100m', '0'], 6.25),  # 100 / (1500+100)
    (['100m', '100m'], 12.5),  # 200 / (1500+100)
    (['100m', '100000000n'], 12.5),  # mixed units # 200 / (1500+100)
    (['100000000n', '0'], 6.25),
    (['100000000n', '100m'], 12.5),
    (['100000000n', '100000000n'], 12.5),
    (['100m', '100000000n'], 12.5),
    (['100000u', '0'], 6.25),
    (['100000u', '100m'], 12.5),
    (['100000u', '100000000n'], 12.5),
    (['100m', '100000u'], 12.5),
])
def test_avg_cpu_percent(
        client, deployment, pods_lookup, metrics, cpu_usage, expected):
    key = (deployment.metadata.labels['app'], deployment.metadata.namespace)
    metrics[key] = mock_podmetric(cpu_usage)
    assert idler.avg_cpu_percent(deployment) == expected


def test_mark_idled(deployment, current_time):
    expected_replicas = deployment.spec.replicas

    idler.mark_idled(deployment)

    assert IDLED in deployment.metadata.labels
    assert IDLED_AT in deployment.metadata.annotations
    assert current_time.isoformat(timespec='seconds') == deployment.metadata.annotations[IDLED_AT]
    assert expected_replicas == deployment.metadata.annotations[REPLICAS_WHEN_UNIDLED]


def test_zero_replicas(deployment):
    idler.zero_replicas(deployment)

    assert deployment.spec.replicas == 0


def test_write_changes(client, deployment):
    idler.write_changes(deployment)

    api = client.AppsV1beta1Api.return_value
    api.patch_namespaced_deployment.assert_called_with(
        deployment.metadata.name,
        deployment.metadata.namespace,
        deployment
    )
