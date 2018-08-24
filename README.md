# Idler
Periodically idles Kubernetes deployments meeting certain criteria to avoid wasting money

## How does it work?

The script performs the following steps:

1. For each [eligible][1] deployment in the cluster, across all namespaces
2. Calculate the [average CPU usage][4] of the deployment's containers over the
   last minute
3. If the usage is greater than a certain [percentage threshold][3], skip to
   the next deployment
4. Otherwise, *idle* the deployment, by:
   1. Adding a label and an annotation to the deployment
   2. Reducing the number of replicas to 0 (which deletes pods)
   3. Disabling the ingress for the deployment, and adding an ingress rule to
      the [unidler][2] ingress for the deployment's hostname (which redirects
      traffic to the [unidler][2] webapp)

## Testing

Build the docker image to run the tests:
```sh
docker build -t idler .
```

## Deployment

Deployed to the kubernetes cluster as a
[cronjob](https://github.com/ministryofjustice/analytics-platform-helm-charts/tree/master/charts/idler) using Helm


[1]: https://github.com/ministryofjustice/analytics-platform-idler/blob/master/idler.py#L109
[2]: https://github.com/ministryofjustice/analytics-platform-unidler
[3]: https://github.com/ministryofjustice/analytics-platform-idler/blob/master/idler.py#L36
[4]: https://github.com/ministryofjustice/analytics-platform-idler/blob/master/idler.py#L140
