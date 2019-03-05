# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.5.2] - 2019-02-18
### Fixed
Updating `Service` correctly.

`Service` redirection needs to set `targetPort`.


## [v0.5.1] - 2019-02-18
### Fixed
Updating `Service` correctly.

There was a mistake in the code which redirected a Kubernetes `Service` to
the Unidler.


## [v0.5.0] - 2019-01-24
### Improvement
Redirect `Service` instead of `Ingress`.

Idling was achieved by disabling the app `Ingress` and adding the app hostname
to the unidler `Ingress`. If multiple users unidled at the same time, there
could be a race condition when removing the hostnames from the unidler `Ingress`.

This change does away with editing ingresses altogether and edits only the app
service. By changing the `Service` to what is essentially a `CNAME` forwarding to
the unidler, requests to the app host are handled by the unidler.


## [v0.4.0] - 2018-10-10
### Improvement
Lookup `Ingress` by App label.

For jupyter-lab support.


## [v0.3.1] - 2018-10-09
### Fixed
Add support for μcores


## [v0.3.0] - 2018-10-03
### Fixed
Support for metrics returned in nanocore units


## [v0.2.4] - 2018-04-27
### Improvements
Added more logging and improved consistency of logging.

[See PR](https://github.com/ministryofjustice/analytics-platform-idler/pull/11)


## [v0.2.3] - 2018-04-25
### Improvements
- Better handling of unhealthy pods (lacking metrics data)
- Fixed logging (and added support for `LOG_LEVEL` environment variable).

See PR: [#10](https://github.com/ministryofjustice/analytics-platform-idler/pull/10)


## [v0.2.2] - 2018-04-25
### Fixed
- Added missing file (`metrics_api.py`) to `Dockerfile`.


## [v0.2.1] - 2018-04-24
### Fixed
- Fixes idler incorrectly idling RStudio instances using more CPU than the threshold (`RSTUDIO_ACTIVIY_CPU_THRESHOLD`).
