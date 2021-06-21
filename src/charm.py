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
import json
import logging
import subprocess

from charms.ingress.v0.ingress import IngressRequires
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class PiholeCharm(CharmBase):
    """Charm the service."""

    name = "pihole"
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        #  self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.pihole_pebble_ready, self.on_pihole_pebble_ready)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.restartdns_action, self.on_restartdns_action)
        self.framework.observe(self.on.getplan_action, self.on_getplan_action)
        self._stored.set_default(webpassword="")

        self.ingress = IngressRequires(self, {
            "service-hostname": self.config["external-hostname"] or self.app.name,
            "service-name": self.app.name,
            "service-port": self.config["service-port"],
        })

    @property
    def container(self):
        """get app container for current unit."""
        return self.unit.get_container(self.name)

    def get_pihole_pebble_layer(self):
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
                    "command": "/s6-init",
                    "startup": "enabled",
                    "environment": env,
                }
            }
        }

    def restart_pihole(self, container):
        pebble_layer = self.get_pihole_pebble_layer()
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("pihole", pebble_layer, combine=True)
        service = container.get_service("pihole")
        if service.is_running():
            logger.debug("stopping service")
            container.stop("pihole")
        logger.debug("starting service")
        container.start("pihole")
        self.unit.status = ActiveStatus()

    def on_pihole_pebble_ready(self, event):
        container = event.workload
        plan = container.get_plan()
        if not plan.services:
            container.add_layer("pihole", self.get_pihole_pebble_layer(), combine=True)
            container.autostart()
        self.unit.status = ActiveStatus()

    def change_webpassword(self, new_password):
        return subprocess.check_call(["pihole", "-a", "-p", new_password])

    def on_config_changed(self, _):
        """config change hook.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        self.ingress.update_config({"service-hostname": self.config["external-hostname"]})
        webpassword = self.config["webpassword"]
        if webpassword != self._stored.webpassword:
            logger.debug("webpassword updated")
            self._stored.webpassword = webpassword
            self.change_webpassword(webpassword)
        container = self.unit.get_container("pihole")
        self.restart_pihole(container)

    def on_restartdns_action(self, event):
        """restartdns in pihole."""
        output = subprocess.check_output(["pihole", "restartdns"]).decode("utf8")
        event.set_results({"restartdns": output})

    def on_getplan_action(self, event):
        """get pebble plan in pihole unit."""
        plan = self.container.get_plan()
        output = json.dumps(plan.to_dict(), indent=4) if plan else ""
        event.set_results({"plan": output})


if __name__ == "__main__":
    main(PiholeCharm)
