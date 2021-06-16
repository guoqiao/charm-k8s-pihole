#!/usr/bin/env python3
# Copyright 2021 guoqiao
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class PiholeCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.show_webpassword_action, self._on_show_webpassword_action)
        self._stored.set_default(webpassword="")

        self.ingress = IngressRequires(self, {
            "service-hostname": self.external_hostname,
            "service-name": self.app.name,
            "service-port": self.service_port,
        })

    @property
    def external_hostname(self):
        return self.config["external-hostname"] or self.app.name

    @property
    def service_port(self):
        return self.config["service-port"]

    def on_install(self, event):
        pass

    def _pihole_pebble_layer(self):
        env = {}
        if self.config["webpassword"]:
            env["WEBPASSWORD"] = self.config["webpassword"]
        # Define an initial Pebble layer configuration
        return {
            "summary": "pihole layer",
            "description": "pebble config layer for pihole",
            "services": {
                "pihole": {
                    "override": "replace",
                    "summary": "pihole",
                    "command": "/s6-init bash",
                    "startup": "enabled",
                    "environment": env,
                }
            }
        }

    def _restart_pihole(self, container):
        pebble_layer = self._pihole_pebble_layer()
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("pihole", pebble_layer, combine=True)
        service = container.get_service("pihole")
        if service.is_running():
            logger.debug("stopping service")
            container.stop("pihole")
        logger.debug("starting service")
        container.start("pihole")
        self.unit.status = ActiveStatus()

    def on_config_changed(self, _):
        """Just an example to show how to deal with changed configuration.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle config, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the config.py file.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        webpassword = self.config["webpassword"]
        if webpassword != self._stored.webpassword:
            logger.debug("webpassword udpated")
            self._stored.webpassword = webpassword
        container = self.unit.get_container("pihole")
        self._restart_pihole(container)

    def _on_show_webpassword_action(self, event):
        """show current webpassword."""
        event.set_results({"show-webpassword": self._stored.webpassword or ""})


if __name__ == "__main__":
    main(PiholeCharm)
