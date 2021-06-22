# Copyright 2021 guoqiao
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock

from charm import PiholeCharm
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(PiholeCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_config_changed(self):
        self.assertEqual(self.harness.charm._stored.webpassword, "")
        self.harness.update_config({"webpassword": "foo"})
        self.assertEqual(self.harness.charm._stored.webpassword, "foo")

    def test_action(self):
        # the harness doesn't (yet!) help much with actions themselves
        action_event = Mock(params={"fail": ""})
        self.harness.charm.run_cmd = Mock(return_value=True)
        self.harness.charm.on_restartdns_action(action_event)

        self.assertTrue(action_event.set_results.called)

    def test_pihole_pebble_ready(self):
        # Check the initial Pebble plan is empty
        initial_plan = self.harness.get_container_pebble_plan("pihole")
        self.assertEqual(initial_plan.to_yaml(), "{}\n")
        # Expected plan after Pebble ready with default config
        expected_plan = {
            "services": {
                "cmd": {
                    "override": "replace",
                    "command": "/usr/local/bin/pihole -a -p pihole",
                    "startup": "disabled",
                },
                "pihole": {
                    "override": "replace",
                    "summary": "pihole",
                    "command": "/s6-init",
                    "startup": "enabled",
                    "environment": {"WEBPASSWORD": "pihole"},
                }
            },
        }
        # Get the pihole container from the model
        container = self.harness.model.unit.get_container("pihole")
        # Emit the PebbleReadyEvent carrying the pihole container
        self.harness.charm.on.pihole_pebble_ready.emit(container)
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan("pihole").to_dict()
        # Check we've got the plan we expected
        self.assertEqual(expected_plan, updated_plan)
        # Check the service was started
        service = self.harness.model.unit.get_container("pihole").get_service("pihole")
        self.assertTrue(service.is_running())
        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
