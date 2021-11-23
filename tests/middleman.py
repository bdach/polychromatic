from _dummy import DummyBackend as DummyBackend

import pylib.common as common
import pylib.locales as locales
import pylib.middleman as middleman
import pylib.preferences as preferences

import os
import unittest


class TestMiddleman(unittest.TestCase):
    """
    Test the middleman against a dummy module to check data flows as expected.
    """
    @classmethod
    def setUpClass(self):
        self._ = locales.Locales("polychromatic").init()
        self.dbg = common.Debugging()
        self.paths = common.paths
        preferences.init(self._)

        self.middleman = middleman.Middleman(self.dbg, common, self._)

        # Override all modules with the dummy
        middleman.BACKEND_NAMES = {"dummy": "Dummy Backend"}
        middleman.BACKEND_MODULES = {"dummy": DummyBackend}
        middleman.TROUBLESHOOT_MODULES = {"dummy": DummyBackend.troubleshoot}
        self.middleman.init()

        if not self.middleman.backends:
            raise RuntimeError("Could not init dummy module!")

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_conditions_ok(self):
        self.assertIsNone(self.middleman.get_backend("openrazer"))

    def test_get_backend(self):
        self.assertIsNotNone(self.middleman.get_backend("dummy"))

    def test_backend_running(self):
        self.assertTrue(self.middleman.is_backend_running("dummy"))

    def test_versions(self):
        self.assertTrue(self.middleman.get_versions()["dummy"], "9.9.9")

    def test_get_devices(self):
        self.assertGreater(len(self.middleman.get_devices()), 0)

    def test_device_cache(self):
        item = self.middleman.get_devices()[0].name = "POSION"
        self.middleman.reload_device_cache()
        self.assertNotEqual(self.middleman.get_devices()[0].name, "POSION")

    def test_get_device_by_name(self):
        device = self.middleman.get_device_by_name("Dummy Headset")
        self.assertEqual(device.serial, "DUMMY0003")

    def test_get_device_by_serial(self):
        device = self.middleman.get_device_by_serial("DUMMY0002")
        self.assertEqual(device.name, "Dummy Mouse")

    def test_get_devices_by_form_factor(self):
        device = self.middleman.get_devices_by_form_factor("keyboard")[0]
        self.assertEqual(device.name, "Dummy Keyboard")

    def test_unsupported_devices(self):
        unknown = self.middleman.get_unsupported_devices()
        self.assertEqual(len(unknown), 3)

    def test_troubleshoot(self):
        # TODO: Incomplete!
        self.skipTest("")

    def test_restart(self):
        self.assertTrue(self.middleman.restart("dummy"))

    def test_active_effect(self):
        # The dummy keyboard's active effect is Static
        device = self.middleman.get_device_by_name("Dummy Keyboard")
        zone = device.zones[0]
        self.assertEqual(self.middleman.get_active_effect(zone), zone.options[1])

    def test_replay_active_effect(self):
        device = self.middleman.get_device_by_name("Dummy Keyboard")
        self.middleman.replay_active_effect(device)

    def test_set_colour_for_option(self):
        device = self.middleman.get_device_by_name("Dummy Keyboard")
        option = device.zones[0].options[1]
        self.middleman.set_colour_for_option(option, "#FF0000")
        self.assertEqual(option.colours[0], "#FF0000")

    def set_colour_for_active_effect_zone(self):
        device = self.middleman.get_device_by_name("Dummy Keyboard")
        expected_option = device.zones[0].options[1]
        zone = device.zones[0]
        self.middleman.set_colour_for_active_effect_zone(zone, "#0000FF")
        self.assertEqual(expected_option.colours[0], "#0000FF")
