#!/usr/bin/env python3
# Copyright 2021 guoqiao
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

import json
import logging

from charms.ingress.v0.ingress import IngressRequires
import ops
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus

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
        self.framework.observe(self.on.set_webpassword_action, self.on_set_webpassword_action)
        self.framework.observe(self.on.restartdns_action, self.on_restartdns_action)
        self.framework.observe(self.on.getplan_action, self.on_getplan_action)
        self._stored.set_default(is_pebble_ready=False)

        self.ingress = IngressRequires(self, {
            "service-hostname": self.config["external-hostname"] or self.app.name,
            "service-name": self.app.name,
            "service-port": self.config["service-port"],
        })

    @property
    def is_pebble_ready(self):
        return self._stored.is_pebble_ready

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
        except ops.pebble.ConnectionError:
            return None

    def is_running(self):
        """Check pihole service is running."""
        return self.service and self.service.is_running()

    def get_pihole_pebble_layer(self):
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
                    "environment": {},
                }
            }
        }

    def restart_pihole(self, container):
        """ensure pihole service is restarted."""

        self.unit.status = MaintenanceStatus("restarting pihole service")
        pebble_layer = self.get_pihole_pebble_layer()
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("pihole", pebble_layer, combine=True)
        service = container.get_service("pihole")
        if not service.is_running():
            logger.debug("service is not running")
            logger.debug("starting service")
            container.start("pihole")
        self.unit.status = ActiveStatus()

    def on_pihole_pebble_ready(self, event):
        logger.info("on_pihole_pebble_ready triggered")
        self._stored.is_pebble_ready = True
        container = event.workload
        container.add_layer("pihole", self.get_pihole_pebble_layer(), combine=True)
        logger.info("pihole layer added, running autostart")
        try:
            container.autostart()
        except ops.pebble.ChangeError as exc:
            # Start service "pihole" (service "pihole" was previously started)
            logger.warning(exc.err)
        self.unit.status = ActiveStatus()

    def run_cmd(self, cmd, label="cmd", env=None):
        """Run a one-off cmd.

        Currently pebble can only run long-live daemon service.
        This function workaround it by checking exception message.
        """
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
            #  Start service "cmd" (cannot start service: exited quickly with code 0)
            if "exited quickly with code 0" in exc.err:
                logger.info("cmd succeed")
                return True
            else:
                logger.exception("cmd failed")
                return False

    def on_config_changed(self, event):
        """charm config changed hook.

        Notes:
        - config-changed may run before pebble-ready
        - multiple config values may be changed at one time
        - config can not be changed from within the charm code

        ref: https://juju.is/docs/sdk/config
        """
        if not self.is_pebble_ready:
            logger.warning("config-changed hook triggered while pebble is not ready, defer event")
            event.defer()
            return

        layer = self.get_pihole_pebble_layer()
        try:
            services = self.container.get_plan().to_dict().get("services", {})
        except ops.pebble.ConnectionError:
            logger.warning("config-changed hook failed to connect pebble, defer event")
            event.defer()
            return

        if services != layer["services"]:
            self.restart_pihole(self.container)

        self.ingress.update_config({"service-hostname": self.config["external-hostname"]})

    def on_set_webpassword_action(self, event):
        """set webpassword for pihole."""
        password = event.params.get("password", "")
        if not password:
            event.fail(message="password can not be empty")
            return

        cmd = "/usr/local/bin/pihole -a -p {}".format(password)
        if self.run_cmd(cmd):
            event.set_results({"set-webpassword": "succeed"})
        else:
            event.fail(message="set webpassword failed")

    def on_restartdns_action(self, event):
        """restartdns in pihole."""
        cmd = "/usr/local/bin/pihole restartdns"
        if self.run_cmd(cmd):
            event.set_results({"restartdns": "succeed"})
        else:
            event.fail(message="restartdns failed")

    def on_getplan_action(self, event):
        """get pebble plan in pihole unit."""
        plan = self.container.get_plan()
        output = json.dumps(plan.to_dict(), indent=4) if plan else ""
        event.set_results({"plan": output})


if __name__ == "__main__":
    main(PiholeCharm)
