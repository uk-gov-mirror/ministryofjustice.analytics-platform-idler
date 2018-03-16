from pprint import pformat

from six import iteritems

import kubernetes
from kubernetes.client.api_client import ApiClient


class MetricsV1beta1Api(object):

    def __init__(self, api_client=None):
        if api_client is None:
            api_client = ApiClient()
        self.api_client = api_client

    def list_pod_metrics_for_all_namespaces(self, **kwargs):
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async'):
            return self.list_pod_metrics_for_all_namespaces_with_http_info(
                **kwargs)
        else:
            (data) = self.list_pod_metrics_for_all_namespaces_with_http_info(
                **kwargs)
            return data

    def list_pod_metrics_for_all_namespaces_with_http_info(self, **kwargs):
        collection_formats = {}

        path_params = {}

        query_params = []
        if '_continue' in kwargs:
            query_params.append(('continue', kwargs['_continue']))
        if 'label_selector' in kwargs:
            query_params.append(('labelSelector', kwargs['label_selector']))

        form_params = []
        local_var_files = {}
        body_params = None

        header_params = {
            'Accept': self.api_client.select_header_accept([
                'application/json',
                'application/yaml',
                'application/vnd.kubernetes.protobuf',
                'application/json;stream=watch',
                'application/vnd.kubernetes.protobuf;stream=watch']),
            'Content-Type': self.api_client.select_header_content_type([
                '*/*']),
        }
        auth_settings = ['BearerToken']

        return self.api_client.call_api(
            f'/apis/metrics.k8s.io/v1beta1/pods',
            'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='MetricsV1beta1PodMetricsList',
            auth_settings=auth_settings,
            async=kwargs.get('async'),
            _return_http_data_only=kwargs.get('_return_http_data_only'),
            _preload_content=kwargs.get('_preload_content', True),
            _request_timeout=kwargs.get('_request_timeout'),
            collection_formats=collection_formats)


kubernetes.client.apis.MetricsV1beta1Api = MetricsV1beta1Api
kubernetes.client.MetricsV1beta1Api = MetricsV1beta1Api


class MetricsV1beta1PodMetricsList(object):
    swagger_types = {
        'api_version': 'str',
        'items': 'list[MetricsV1beta1PodMetrics]',
        'kind': 'str',
        'metadata': 'V1ListMeta'
    }

    attribute_map = {
        'api_version': 'apiVersion',
        'items': 'items',
        'kind': 'kind',
        'metadata': 'metadata'
    }

    def __init__(self, api_version=None, items=None, kind=None, metadata=None):
        self.api_version = api_version
        self.items = items
        self.kind = kind
        self.metadata = metadata
        self.discriminator = None

    def to_dict(self):
        result = {}
        for attr, _ in iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, 'to_dict') else x,
                    value
                ))
            elif hasattr(value, 'to_dict'):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], 'to_dict') else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        return pformat(self.to_dict())

    def __repr__(self):
        return self.to_str()

    def __eq__(self, other):
        if not isinstance(other, MetricsV1beta1PodMetricsList):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other


kubernetes.client.models.MetricsV1beta1PodMetricsList = \
    MetricsV1beta1PodMetricsList
kubernetes.client.MetricsV1beta1PodMetricsList = MetricsV1beta1PodMetricsList


class MetricsV1beta1PodMetrics(object):
    swagger_types = {
        'containers': 'list[MetricsV1beta1ContainerMetrics]',
        'metadata': 'V1ObjectMeta',
        'timestamp': 'datetime',
        'window': 'str',
    }

    attribute_map = {
        'containers': 'containers',
        'metadata': 'metadata',
        'timestamp': 'timestamp',
        'window': 'window',
    }

    def __init__(self, containers=None, metadata=None, timestamp=None, window=None):
        self.containers = containers
        self.metadata = metadata
        self.timestamp = timestamp
        self.window = window
        self.discriminator = None

    def to_dict(self):
        result = {}
        for attr, _ in iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, 'to_dict') else x,
                    value
                ))
            elif hasattr(value, 'to_dict'):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], 'to_dict') else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        return pformat(self.to_dict())

    def __repr__(self):
        return self.to_str()

    def __eq__(self, other):
        if not isinstance(other, MetricsV1beta1PodMetrics):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

kubernetes.client.models.MetricsV1beta1PodMetrics = MetricsV1beta1PodMetrics
kubernetes.client.MetricsV1beta1PodMetrics = MetricsV1beta1PodMetrics


class MetricsV1beta1ContainerMetrics(object):
    swagger_types = {
        'name': 'str',
        'usage': 'dict(str, str)',
    }

    attribute_map = {
        'name': 'name',
        'usage': 'usage',
    }

    def __init__(self, name=None, usage=None):
        self.name = name
        self.usage = usage
        self.discriminator = None

    def to_dict(self):
        result = {}
        for attr, _ in iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, 'to_dict') else x,
                    value
                ))
            elif hasattr(value, 'to_dict'):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], 'to_dict') else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        return pformat(self.to_dict())

    def __repr__(self):
        return self.to_str()

    def __eq__(self, other):
        if not isinstance(other, MetricsV1beta1ContainerMetrics):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

kubernetes.client.models.MetricsV1beta1ContainerMetrics = MetricsV1beta1ContainerMetrics
kubernetes.client.MetricsV1beta1ContainerMetrics = MetricsV1beta1ContainerMetrics

