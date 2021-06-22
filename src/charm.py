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
import uuid

from charms.ingress.v0.ingress import IngressRequires
import ops
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
        try:
            return self.unit.get_container(self.name)
        except ops.model.ModelError:
            return None

    @property
    def service(self):
        try:
            return self.container.get_service(self.name)
        except ops.model.ModelError:
            return None

    def is_running(self):

        return self.service.is_running() if self.service else False

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
        else:
            logger.debug("service is not running")
        logger.debug("starting service")
        container.start("pihole")
        self.unit.status = ActiveStatus()

    def run_cmd(self, cmd, label="cmd", env=None):
        layer = {
            "services": {
                label: {
                    "override": "replace",
                    "startup": "disabled",
                    "command": cmd,
                    "environment": env or {},
                }
            }
        }
        logger.info("running cmd: %s", cmd)
        self.container.add_layer(label, layer, combine=True)

        try:
            self.container.start(label)
        except ops.pebble.ChangeError as exc:
            summary = exc.change.summary
            #  Start service "cmd" (cannot start service: exited quickly with code 0)
            if "exited quickly with code 0" in exc.err:
                logger.info("cmd succeed: %s", cmd)
                return True
            else:
                logger.exception("cmd failed")
                return False

    def on_pihole_pebble_ready(self, event):
        container = event.workload
        plan = container.get_plan()
        if not plan.services:
            container.add_layer("pihole", self.get_pihole_pebble_layer(), combine=True)
            logger.info("pihole layer added")
            container.autostart()
            self.change_webpassword(self.config["webpassword"])
        self.unit.status = ActiveStatus()

    def change_webpassword(self, new_password):
        if new_password:
            cmd = "/usr/local/bin/pihole -a -p {}".format(new_password)
            self.run_cmd(cmd)
        else:
            logger.warning("new password is empty, no change made")

    def on_config_changed(self, _):
        """config change hook.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        self.ingress.update_config({"service-hostname": self.config["external-hostname"]})
        if self.is_running():
            webpassword = self.config["webpassword"]
            if webpassword != self._stored.webpassword:
                logger.debug("webpassword updated")
                self._stored.webpassword = webpassword
                self.change_webpassword(webpassword)
            # container = self.unit.get_container("pihole")
            # self.restart_pihole(container)
        else:
            logger.warning("pihole service is not running")

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
