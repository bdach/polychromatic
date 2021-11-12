#!/usr/bin/python3
#
# Polychromatic is licensed under the GPLv3.
# Copyright (C) 2020-2021 Luke Horwell <code@horwell.me>
#
"""
This module collates data from installed backends for supported devices.
Polychromatic's applications will process this data.

Each backend is stored in its own module adjacent to this file. These are
written by inheriting the "Backend" class in _backend.py below and
implemented accordingly.

Refer to the online documentation for more details:
https://docs.polychromatic.app/
"""

from . import procpid
from . import common
from .backends._backend import Backend

from .backends import openrazer as openrazer_backend
from .troubleshoot import openrazer as openrazer_troubleshoot

BACKEND_NAMES = {
#   "backend ID": "human readable string"
    "openrazer": "OpenRazer"
}

BACKEND_MODULES = {
    "openrazer": openrazer_backend.OpenRazerBackend
}

TROUBLESHOOT_MODULES = {
    "openrazer": openrazer_troubleshoot.troubleshoot
}


class Middleman(object):
    """
    The 'middleman' that processes the data between Polychromatic's applications
    by blending all the backends together.
    """
    def __init__(self, dbg, common, _):
        """
        Stores variables for the sessions.
        """
        self._dbg = dbg
        self._common = common
        self._ = _

        # List of initialized Backend() objects.
        self.backends = []

        # List of Backend() modules that failed to init().
        self.bad_init = []

        # List of backend IDs that are not present.
        self.not_installed = []

        # Dictionary of Backend IDs referencing troubleshoot() functions, if available.
        self.troubleshooters = {}

        # Keys containing human readable strings for modules that failed to import.
        self.import_errors = {}

        # Dictionary of Backend IDs referencing a list of DeviceItem() objects.
        self.device_cache = []

    def init(self):
        """
        Initialise the backend objects. This should be called when the user interface
        is ready. Note that this thread may potentially block depending on how fast
        the backends load.
        """
        def _load_backend_module(backend_id):
            try:
                module = BACKEND_MODULES[backend_id]
                backend = module(self._dbg, self._common, self._)
                if backend.init():
                    self.backends.append(backend)
                else:
                    self.bad_init.append(backend)
            except (ImportError, ModuleNotFoundError):
                self.not_installed.append(backend_id)
            except Exception as e:
                self.import_errors[backend_id] = self._common.get_exception_as_string(e)

            try:
                self.troubleshooters[backend_id] = TROUBLESHOOT_MODULES[backend_id]
            except NameError:
                # Backend does not have a troubleshooter.
                pass

        for backend_id in BACKEND_NAMES.keys():
            _load_backend_module(backend_id)

    def get_backend(self, backend_id):
        """
        Returns a specific backend. If not loaded, returns None.
        """
        for module in self.backends:
            if module.backend_id == backend_id:
                return module
        return None

    def is_backend_running(self, backend_id):
        """
        Returns a boolean to indicate whether a specific backend ID is running
        and was successfully initialized.
        """
        for module in self.backends:
            if module.backend_id == backend_id:
                return True
        return False

    def get_versions(self):
        """
        Return a dictionary of versions for each running backend.
        """
        versions = {}
        for module in self.backends:
            versions[module.backend_id] = module.version
        return versions

    def _reload_device_cache_if_empty(self):
        """
        Reload the cache of DeviceItem()'s if it has not initalized yet.
        """
        if self.device_cache:
            return

        for module in self.backends:
            device_list = module.get_devices()
            if type(device_list) == list:
                self.device_cache = self.device_cache + device_list

    def reload_device_cache(self):
        """
        Clear the device object cache and reload.
        """
        self.device_cache = []
        self._reload_device_cache_if_empty()

    def get_devices(self):
        """
        Returns a list of DeviceItem() objects.
        """
        self._reload_device_cache_if_empty()
        return self.device_cache

    def get_device_by_name(self, name):
        """
        Returns a fresh DeviceItem() by looking up its device name, or None if
        there is no device with that name.
        """
        for backend in self.backends:
            device = backend.get_device_by_name(name)
            if isinstance(device, Backend.DeviceItem):
                return device
        return None

    def get_device_by_serial(self, serial):
        """
        Returns a fresh DeviceItem() object by looking up its serial number, or
        None if there is no device with that serial string.
        """
        for backend in self.backends:
            device = backend.get_device_by_serial(serial)
            if isinstance(device, Backend.DeviceItem):
                return device
        return None

    def get_device_by_form_factor(self, form_factor_id):
        """
        Returns a list of DeviceItem()'s based on the form factor specified, or empty list.
        """
        self._reload_device_cache_if_empty()
        devices = []
        for device in self.device_cache:
            if device.form_factor["id"] == form_factor_id:
                devices.append(device)
        return devices

    def get_unsupported_devices(self):
        """
        Returns a list of connected devices that cannot be controlled by their backend.
        """
        unknown_devices = []
        for backend in self.backends:
            unknown_devices = unknown_devices + backend.get_unsupported_devices()
        return unknown_devices

    def troubleshoot(self, backend, i18n, fn_progress_set_max, fn_progress_advance):
        """
        Performs a series of troubleshooting steps to identify possible
        reasons why a particular backend is non-functional.

        Params:
            backend         (str)       ID of backend to check
            i18n            (obj)       _ function for translating strings

        Returns:
            (list)          Results from the troubleshooter
            None            Troubleshooter not available
            False           Troubleshooter failed
        """
        try:
            return self.troubleshooters[backend](i18n, fn_progress_set_max, fn_progress_advance)
        except KeyError:
            # Troubleshooter not available for this backend
            return None
        except Exception as e:
            # Troubleshooter crashed
            return common.get_exception_as_string(e)

    def restart(self, backend):
        """
        Restarts a specific backend.
        """
        for module in self.backends:
            if module.backend_id == backend:
                return module.restart()

    def _get_current_device_option(self, device, zone=None):
        """
        Return the currently 'active' option, its parameter and colour(s), if applicable.
        Usually this would be an effect.

        Params:
            device          (dict)      middleman.get_device() object
            zone            (str)       (Optional) Get data for this specific zone.

        Returns list:
        [option_id, option_data, colour_hex]
        """
        option_id = None
        option_data = None
        colour_hex = []
        colour_count = 0
        found_option = None
        param = None

        if zone:
            zones = [zone]
        else:
            # Find an active effect in all zones, uses the last matched one.
            zones = device["zone_options"].keys()

        for zone in zones:
            for option in device["zone_options"][zone]:
                if not "active" in option.keys():
                    continue

                if not option["type"] == "effect":
                    continue

                if option["active"] == True:
                    found_option = option
                    option_id = option["id"]

                    try:
                        if len(option["parameters"]) == 0:
                            break
                        else:
                            for param in option["parameters"]:
                                if param["active"] == True:
                                    option_data = param["data"]
                                    colour_hex = param["colours"]
                    except KeyError:
                        # Toggle or slider do not have a 'parameters' key
                        pass

        if not found_option:
            return [None, None, None]

        if not param:
            colour_hex = found_option["colours"]

        return [option_id, option_data, colour_hex]

    def replay_active_effect(self, backend, uid, zone):
        """
        Replays the 'active' effect. This may be used, for example, to restore
        the effect that was being played before the matrix was tested or being
        previewed in the editor.
        """
        print("fixme:replay_active_effect")
        return
        device = self.get_device(backend, uid)
        serial = device["serial"]
        state = procpid.DeviceSoftwareState(serial)

        # Device was playing a software effect, resume that.
        effect = state.get_effect()
        if effect:
            procmgr = procpid.ProcessManager("helper")
            procmgr.start_component(["--run-fx", effect["path"], "--device-serial", serial])
            return

        # Device was set to a hardware effect, apply that.
        option_id, option_data, colour_hex = self._get_current_device_option(device, zone)
        if option_id:
            return self.set_device_state(backend, uid, device["serial"], zone, option_id, option_data, colour_hex)

    def set_device_colour(self, device, zone, hex_value, colour_pos=0):
        """
        Re-apply the currently selected options with a new primary colour.

        The return code is the same as set_device_state()
        """
        print("fixme:set_device_colour")
        return

        option_id, option_data, colour_hex = self._get_current_device_option(device, zone)
        if not colour_hex:
            return False
        colour_hex[colour_pos] = hex_value
        return self.set_device_state(device["backend"], device["uid"], device["serial"], zone, option_id, option_data, colour_hex)

    def set_bulk_option(self, option_id, option_data, colours_needed):
        """
        The "Apply to All" function that will set all of the devices to the specified
        effect (option ID and option parameter), such as "breath" and "single", or
        "static" and None.

        The colour for the device will be re-used from a previous selection.

        Params:
            option_id           (str)
            option_data         (str)
            colours_needed      (int)

        Parameters may be determined by the common.get_bulk_apply_options() function.

        Return is null.
        """
        self._dbg.stdout("Setting all devices to '{0}' (parameter: {1})".format(option_id, option_data), self._dbg.action, 1)

        devices = self.get_device_all()
        for device in devices:
            name = device["name"]
            backend = device["backend"]
            uid = device["uid"]
            serial = device["serial"]
            colour_hex = []

            for zone in device["zone_options"].keys():
                # Skip if the device's zone/options doesn't support this request
                skip = True
                for option in device["zone_options"][zone]:
                    if option["id"] == option_id:
                        skip = False
                        colour_hex = option["colours"]
                        break

                if skip:
                    continue

                # TODO: Use default colours
                while len(colour_hex) < colours_needed:
                    colour_hex.append("#00FF00")

                self._dbg.stdout("- {0} [{1}]".format(name, zone), self._dbg.action, 1)
                result = self.set_device_state(backend, uid, serial, zone, option_id, option_data, colour_hex)
                if result == True:
                    self._dbg.stdout("Request OK", self._dbg.success, 1)
                elif result == False:
                    self._dbg.stdout("Bad request!", self._dbg.error, 1)
                else:
                    self._dbg.stdout("Error: " + str(result), self._dbg.error, 1)

    def set_bulk_colour(self, new_colour_hex):
        """
        The "Apply to All" function that will set all of the devices to the specified
        primary colour. Some devices may not be playing an effect that uses a colour
        (e.g. wave, spectrum) and as such, this will cause no effect.

        Params:
            new_colour_hex      (str)

        Return is null.
        """
        self._dbg.stdout("Setting all primary colours to {0}".format(new_colour_hex), self._dbg.action, 1)

        devices = self.get_device_all()
        for device in devices:
            option_id, option_data, colour_hex = self._get_current_device_option(device)
            name = device["name"]
            backend = device["backend"]
            uid = device["uid"]
            serial = device["serial"]

            # Skip devices that do not support this option
            if not option_id:
                continue

            for zone in device["zone_options"].keys():
                # Skip if the device's zone/options doesn't support this request
                skip = True
                for option in device["zone_options"][zone]:
                    if option["id"] == option_id:
                        skip = False
                        break

                    if not option["colours"]:
                        continue

                if skip:
                    continue

                self._dbg.stdout("- {0} [{1}]".format(name, zone), self._dbg.action, 1)
                result = self.set_device_colour(device, zone, new_colour_hex)
                if result == True:
                    self._dbg.stdout("Request OK", self._dbg.success, 1)
                elif result == False:
                    self._dbg.stdout("Bad request!", self._dbg.error, 1)
                else:
                    self._dbg.stdout("Error: " + str(result), self._dbg.error, 1)
