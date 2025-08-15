#  Copyright (C) 2024 The Android Open Source Project
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

# Lint as: python3
"""Wi-Fi Aware Latency test reimplemented in Mobly."""
import logging
import sys
import time
import json
import queue
import os

from android.platform.test.annotations import ApiTest
from aware import aware_lib_utils as autils
from aware import constants
from mobly import asserts
from mobly import base_test
from mobly import records
from mobly import test_runner
from mobly import utils
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import callback_handler_v2
from mobly.snippet import callback_event
# from queue import Empty


RUNTIME_PERMISSIONS = (
    'android.permission.ACCESS_FINE_LOCATION',
    'android.permission.ACCESS_COARSE_LOCATION',
    'android.permission.NEARBY_WIFI_DEVICES',
)
PACKAGE_NAME = constants.WIFI_AWARE_SNIPPET_PACKAGE_NAME
_DEFAULT_TIMEOUT = constants.WAIT_WIFI_STATE_TIME_OUT.total_seconds()
_CALLBACK_NAME = constants.DiscoverySessionCallbackParamsType.CALLBACK_NAME
_TRANSPORT_TYPE_WIFI_AWARE = (
    constants.NetworkCapabilities.Transport.TRANSPORT_WIFI_AWARE
)

_NETWORK_CB_KEY_NETWORK_SPECIFIER = "network_specifier"
_NETWORK_CB_LINK_PROPERTIES_CHANGED = (
    constants.NetworkCbName.ON_PROPERTIES_CHANGED)
_NETWORK_CB_KEY_INTERFACE_NAME = "interfaceName"

# Aware Data-Path Constants
_DATA_PATH_INITIATOR = 0
_DATA_PATH_RESPONDER = 1

# Publish & Subscribe Config keys.
_PUBLISH_TYPE_UNSOLICITED = 0
_PUBLISH_TYPE_SOLICITED = 1
_SUBSCRIBE_TYPE_PASSIVE = 0
_SUBSCRIBE_TYPE_ACTIVE = 1

_REQUEST_NETWORK_TIMEOUT_MS = 15 * 1000


class WifiAwarelatencytest(base_test.BaseTestClass):
    """Set of tests for Wi-Fi Aware Latency."""

    # message ID counter to make sure all uses are unique
    msg_id = 0

    # number of second to 'reasonably' wait to make sure that devices synchronize
    # with each other - useful for OOB test cases, where the OOB discovery would
    # take some time
    WAIT_FOR_CLUSTER = 5

    SERVICE_NAME = "GoogleTestServiceXYZ"

    ads: list[android_device.AndroidDevice]
    publisher: android_device.AndroidDevice
    subscriber: android_device.AndroidDevice



    def setup_class(self):
        # Register two Android devices.
        self.ads = self.register_controller(android_device, min_number=2)
        self.publisher = self.ads[0]
        self.subscriber = self.ads[1]

        def setup_device(device: android_device.AndroidDevice):
            device.load_snippet(
                'wifi_aware_snippet', PACKAGE_NAME
            )
            for permission in RUNTIME_PERMISSIONS:
                device.adb.shell(['pm', 'grant', PACKAGE_NAME, permission])
            asserts.abort_all_if(
                not device.wifi_aware_snippet.wifiAwareIsAvailable(),
                f'{device} Wi-Fi Aware is not available.',
            )

        # Set up devices in parallel.
        utils.concurrent_exec(
            setup_device,
            ((self.publisher,), (self.subscriber,)),
            max_workers=2,
            raise_on_exception=True,
        )

    def setup_test(self):
        for ad in self.ads:
            autils.control_wifi(ad, True)
            aware_avail = ad.wifi_aware_snippet.wifiAwareIsAvailable()
            if not aware_avail:
                ad.log.info('Aware not available. Waiting ...')
                state_handler = (
                    ad.wifi_aware_snippet.wifiAwareMonitorStateChange())
                state_handler.waitAndGet(
                    constants.WifiAwareBroadcast.WIFI_AWARE_AVAILABLE)

    def teardown_test(self):
        utils.concurrent_exec(
            self._teardown_test_on_device,
            ((self.publisher,), (self.subscriber,)),
            max_workers=2,
            raise_on_exception=True,
        )
        utils.concurrent_exec(
            lambda d: d.services.create_output_excerpts_all(
                self.current_test_info),
            param_list=[[ad] for ad in self.ads],
            raise_on_exception=True,
        )

    def _teardown_test_on_device(
            self, ad: android_device.AndroidDevice) -> None:
        ad.wifi_aware_snippet.wifiAwareCloseAllWifiAwareSession()
        ad.wifi_aware_snippet.connectivityReleaseAllSockets()
        if ad.is_adb_root:
          autils.reset_device_parameters(ad)
          autils.validate_forbidden_callbacks(ad)
          autils.reset_device_statistics(ad)

    def on_fail(self, record: records.TestResult) -> None:
        android_device.take_bug_reports(self.ads,
                                        destination =
                                        self.current_test_info.output_path)


    def _start_attach(self, ad: android_device.AndroidDevice) -> str:
        """Starts the attach process on the provided device."""
        handler = ad.wifi_aware_snippet.wifiAwareAttach()
        attach_event = handler.waitAndGet(
            event_name = constants.AttachCallBackMethodType.ATTACHED,
            timeout = _DEFAULT_TIMEOUT,
        )
        asserts.assert_true(
            ad.wifi_aware_snippet.wifiAwareIsSessionAttached(handler.callback_id),
            f'{ad} attach succeeded, but Wi-Fi Aware session is still null.'
        )
        ad.log.info('Attach Wi-Fi Aware session succeeded.')
        return attach_event.callback_id

    def start_discovery_session(self, dut, session_id, is_publish, dtype, instant_mode = None):
        """Start a discovery session

        Args:
            dut: Device under test
            session_id: ID of the Aware session in which to start discovery
            is_publish: True for a publish session, False for subscribe session
            dtype: Type of the discovery session
            instant_mode: set the channel to use instant communication mode.

        Returns:
        Discovery session started event.
        """
        config = {}
        config[constants.SERVICE_NAME] ="GoogleTestServiceXY"
        if instant_mode is not None:
            config[constants.INSTANTMODE_ENABLE] = instant_mode
        if is_publish:
            config[constants.PUBLISH_TYPE] = dtype
            disc_id = dut.wifi_aware_snippet.wifiAwarePublish(
                session_id, config
            )
            discovery = disc_id.waitAndGet(
                constants.DiscoverySessionCallbackMethodType.DISCOVER_RESULT)
            callback_name = discovery.data[_CALLBACK_NAME]
            asserts.assert_equal(
                constants.DiscoverySessionCallbackMethodType.PUBLISH_STARTED,
                callback_name,
                f'{dut} publish failed, got callback: {callback_name}.',
            )
        else:
            config[constants.SUBSCRIBE_TYPE] = dtype
            disc_id = dut.wifi_aware_snippet.wifiAwareSubscribe(
                session_id, config
            )
            discovery = disc_id.waitAndGet(
                constants.DiscoverySessionCallbackMethodType.DISCOVER_RESULT)
            callback_name = discovery.data[_CALLBACK_NAME]
            asserts.assert_equal(
                constants.DiscoverySessionCallbackMethodType.SUBSCRIBE_STARTED,
                callback_name,
                f'{dut} subscribe failed, got callback: {callback_name}.',
            )
        return disc_id, discovery


    def run_synchronization_latency(self, results, do_unsolicited_passive,
                                    dw_24ghz, dw_5ghz, num_iterations,
                                    startup_offset, timeout_period):
        """Run the synchronization latency test with the specified DW intervals.
        There is no direct measure of synchronization. Instead starts a discovery
        session as soon as possible and measures both probability of discovery
        within a timeout period and the actual discovery time (not necessarily
        accurate).

        Args:
        results: Result array to be populated - will add results (not erase it)
        do_unsolicited_passive: True for unsolicited/passive, False for
                              solicited/active.
        dw_24ghz: DW interval in the 2.4GHz band.
        dw_5ghz: DW interval in the 5GHz band.
        num_iterations: number of the iterations.
        startup_offset: The start-up gap (in seconds) between the two devices
        timeout_period: Time period over which to measure synchronization
        """
        key = "%s_dw24_%d_dw5_%d_offset_%d" % ("unsolicited_passive"
                                               if do_unsolicited_passive else
                                               "solicited_active", dw_24ghz,
                                               dw_5ghz, startup_offset)
        results[key] = {}
        results[key]["num_iterations"] = num_iterations
        self.publisher.pretty_name = "Publisher"
        self.subscriber.pretty_name ="Subscriber"
        autils.config_power_settings(self.publisher, dw_24ghz, dw_5ghz)
        autils.config_power_settings(self.subscriber, dw_24ghz, dw_5ghz)
        latencies = []
        failed_discoveries = 0
        for i in range(num_iterations):
            # Publisher+Subscriber: attach and wait for confirmation
            p_id = self._start_attach(self.publisher)
            s_id = self._start_attach(self.subscriber)
            # start publish
            p_disc_id, p_disc_event = self.start_discovery_session(
                self.publisher, p_id, True, _PUBLISH_TYPE_UNSOLICITED
                if do_unsolicited_passive else _PUBLISH_TYPE_SOLICITED)

            # start subscribe
            s_disc_id, s_session_event = self.start_discovery_session(
                self.subscriber, s_id, False, _SUBSCRIBE_TYPE_PASSIVE
                if do_unsolicited_passive else _SUBSCRIBE_TYPE_ACTIVE)
            # wait for discovery (allow for failures here since running lots of
            # samples and would like to get the partial data even in the presence of
            # errors)
            try:
                discovered_event = s_disc_id.waitAndGet(
                    constants.DiscoverySessionCallbackMethodType.SERVICE_DISCOVERED,
                    timeout_period)
                logging.info(
                    "[Subscriber] SESSION_CB_ON_SERVICE_DISCOVERED: %s",
                    discovered_event.data)
            except queue.Empty:
                failed_discoveries = failed_discoveries + 1
                continue
            finally:
                self.publisher.wifi_aware_snippet.wifiAwareDetach(p_id)
                self.subscriber.wifi_aware_snippet.wifiAwareDetach(s_id)
                self.publisher.wifi_aware_snippet.wifiAwareCloseDiscoverSession(
                    p_disc_id.callback_id)
                self.subscriber.wifi_aware_snippet.wifiAwareCloseDiscoverSession(
                    s_disc_id.callback_id)
            # collect latency information
            latencies.append(
                discovered_event.data["timestampMs"] - s_session_event.data["timestampMs"]
            )

        autils.extract_stats(self.subscriber,
                             data=latencies,
                             results=results[key],
                             key_prefix="",
                             log_prefix="Subscribe Session Sync/Discovery (%s, dw24=%d, dw5=%d)"
                                        % ("Unsolicited/Passive" if do_unsolicited_passive else
                                           "Solicited/Active", dw_24ghz, dw_5ghz))
        logging.info("results %s", results)
        results[key]["num_failed_discovery"] = failed_discoveries
        logging.info("failed_discoveries %s", failed_discoveries)

    def run_discovery_latency(self, results, do_unsolicited_passive, dw_24ghz,
                              dw_5ghz, num_iterations, csv_name="latency_test"):
        """Run the service discovery latency test with the specified DW intervals.

        Args:
            results: Result array to be populated -
                     will add results (not erase it)
            do_unsolicited_passive: True for unsolicited/passive, False for
                                    solicited/active.
            dw_24ghz: DW interval in the 2.4GHz band.
            dw_5ghz: DW interval in the 5GHz band.
            num_iterations: number of the iterations.
            csv_name: csv file test result name.
        """
        key = "%s_dw24_%d_dw5_%d" % ("unsolicited_passive"
                                     if do_unsolicited_passive else
                                     "solicited_active", dw_24ghz, dw_5ghz)
        results[key] = {}
        results[key]["num_iterations"] = num_iterations
        p_dut = self.ads[0]
        p_dut.pretty_name = "Publisher"
        s_dut = self.ads[1]
        s_dut.pretty_name ="Subscriber"
        # override the default DW configuration
        autils.config_power_settings(p_dut, dw_24ghz, dw_5ghz)
        autils.config_power_settings(s_dut, dw_24ghz, dw_5ghz)
        # Publisher+Subscriber: attach and wait for confirmation
        p_id = self._start_attach(p_dut)
        # start publish
        p_disc_id, p_disc_event = self.start_discovery_session(
            self.publisher, p_id, True, _PUBLISH_TYPE_UNSOLICITED
            if do_unsolicited_passive else _PUBLISH_TYPE_SOLICITED)
        time.sleep(10)
        # loop, perform discovery, and collect latency information
        latencies = []
        failed_discoveries = 0
        for i in range(num_iterations):
            s_id = self._start_attach(s_dut)
            s_disc_id, s_session_event = self.start_discovery_session(
                self.subscriber, s_id, False, _SUBSCRIBE_TYPE_PASSIVE
                if do_unsolicited_passive else _SUBSCRIBE_TYPE_ACTIVE)
            try:
                discovered_event = s_disc_id.waitAndGet(
                    constants.DiscoverySessionCallbackMethodType.SERVICE_DISCOVERED,
                    10)
                logging.info(
                    "[Subscriber] SESSION_CB_ON_SERVICE_DISCOVERED: %s",
                    discovered_event.data)
            except queue.Empty:
                failed_discoveries = failed_discoveries + 1
                continue
            finally:
                self.subscriber.wifi_aware_snippet.wifiAwareDetach(s_id)

            # collect latency information
            latencies.append(
                discovered_event.data["timestampMs"] - s_session_event.data["timestampMs"]
            )
            s_dut.wifi_aware_snippet.wifiAwareCloseDiscoverSession(
                s_disc_id.callback_id)
        filename = f"{csv_name}.csv"
        output_file = os.path.join(self.log_path, filename)
        autils.extract_stats(s_dut,
                             data=latencies,
                             results=results[key],
                             key_prefix="",
                             log_prefix="Subscribe Session Sync/Discovery (%s, dw24=%d, dw5=%d)"
                                        % ("Unsolicited/Passive" if do_unsolicited_passive else
                                           "Solicited/Active", dw_24ghz, dw_5ghz),
                             csv_filepath=output_file)
        results[key]["num_failed_discovery"] = failed_discoveries
        logging.info("How many times for failed discovery %s times", failed_discoveries)
        # Publisher+Subscriber: Terminate sessions
        p_dut.wifi_aware_snippet.wifiAwareCloseDiscoverSession(
            p_disc_id.callback_id)


    ####################################################
    #  Wi-Fi Aware synchronization latency test:
    #
    # names is: test_synchronization_default_dws/non_interactive_dws
    # where:
    # results: Result array to be populated - will add results (not erase it)
    # do_unsolicited_passive: True for unsolicited/passive, False for
    #                          solicited/active.
    # dw_24ghz: DW interval in the 2.4GHz band.
    # dw_5ghz: DW interval in the 5GHz band.
    # num_iterations: number of the iterations.
    # startup_offset: The start-up gap (in seconds) between the two devices
    # timeout_period: Time period over which to measure synchronization
    ####################################################

    @ApiTest(
        apis=[
            'android.net.wifi.aware.WifiAwareManager#attach('
            'android.net.wifi.aware.AttachCallback,'
            'android.net.wifi.aware.IdentityChangedListener,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#publish('
            'android.net.wifi.aware.PublishConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#subscrible('
            'android.net.wifi.aware.SubscribeConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareNetworkSpecifier.Builder#build',
            'android.net.wifi.aware.WifiAwareSession#createNetworkSpecifierOpen(byte[])',
        ]
    )

    def test_synchronization_default_dws(self):
        """Measure the device synchronization for default dws. Loop over values
        from 0 to 4 seconds."""
        results = {}
        for startup_offset in range(5):
            self.run_synchronization_latency(
                results=results,
                do_unsolicited_passive=True,
                dw_24ghz=constants.AwarePowerSettings.POWER_DW_24_INTERACTIVE,
                dw_5ghz=constants.AwarePowerSettings.POWER_DW_5_INTERACTIVE,
                num_iterations=10,
                startup_offset=startup_offset,
                timeout_period=20)
        asserts.explicit_pass(
            "test_synchronization_default_dws finished", extras=results)
        autils.save_results_to_json(results, "synchronization_default_dws.json" )

    @ApiTest(
        apis=[
            'android.net.wifi.aware.WifiAwareManager#attach('
            'android.net.wifi.aware.AttachCallback,'
            'android.net.wifi.aware.IdentityChangedListener,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#publish('
            'android.net.wifi.aware.PublishConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#subscrible('
            'android.net.wifi.aware.SubscribeConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareNetworkSpecifier.Builder#build',
            'android.net.wifi.aware.WifiAwareSession#createNetworkSpecifierOpen(byte[])',
        ]
    )

    def test_synchronization_non_interactive_dws(self):
        """Measure the device synchronization for non-interactive dws. Loop over
    values from 0 to 4 seconds."""
        results = {}
        for startup_offset in range(5):
            self.run_synchronization_latency(
                results=results,
                do_unsolicited_passive=True,
                dw_24ghz=(
                    constants.AwarePowerSettings.POWER_DW_24_NON_INTERACTIVE),
                dw_5ghz=(
                    constants.AwarePowerSettings.POWER_DW_5_NON_INTERACTIVE),
                num_iterations=10,
                startup_offset=startup_offset,
                timeout_period=20)
        asserts.explicit_pass(
            "test_synchronization_non_interactive_dws finished",
            extras=results)

    ####################################################
    #  Wi-Fi Aware discovery latency test:
    #
    # names is: test_discovery_latency_default_dws/non_interactive_dws/_all_dws
    #
    # where:
    # results: Result array to be populated -
    #          will add results (not erase it)
    # do_unsolicited_passive: True for unsolicited/passive, False for
    #                         solicited/active.
    # dw_24ghz: DW interval in the 2.4GHz band.
    # dw_5ghz: DW interval in the 5GHz band.
    # num_iterations: number of the iterations.
    # csv_name: csv file test result name.
    ####################################################

    @ApiTest(
        apis=[
            'android.net.wifi.aware.WifiAwareManager#attach('
            'android.net.wifi.aware.AttachCallback,'
            'android.net.wifi.aware.IdentityChangedListener,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#publish('
            'android.net.wifi.aware.PublishConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#subscrible('
            'android.net.wifi.aware.SubscribeConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareNetworkSpecifier.Builder#build',
            'android.net.wifi.aware.WifiAwareSession#createNetworkSpecifierOpen(byte[])',
        ]
    )

    def test_discovery_latency_default_dws(self):
        """Measure the service discovery latency with the default DW configuration.
    """
        results = {}
        self.run_discovery_latency(
            results=results,
            do_unsolicited_passive=True,
            dw_24ghz=constants.AwarePowerSettings.POWER_DW_24_INTERACTIVE,
            dw_5ghz=constants.AwarePowerSettings.POWER_DW_5_INTERACTIVE,
            num_iterations=100,
            csv_name="test_discovery_default_dws")
        asserts.explicit_pass(
            "test_discovery_latency_default_parameters finished",
            extras=results)

    @ApiTest(
        apis=[
            'android.net.wifi.aware.WifiAwareManager#attach('
            'android.net.wifi.aware.AttachCallback,'
            'android.net.wifi.aware.IdentityChangedListener,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#publish('
            'android.net.wifi.aware.PublishConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#subscrible('
            'android.net.wifi.aware.SubscribeConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareNetworkSpecifier.Builder#build',
            'android.net.wifi.aware.WifiAwareSession#createNetworkSpecifierOpen(byte[])',
        ]
    )

    def test_discovery_latency_non_interactive_dws(self):
        """Measure the service discovery latency with the DW configuration for non
    -interactive mode (lower power)."""
        results = {}
        self.run_discovery_latency(
            results=results,
            do_unsolicited_passive=True,
            dw_24ghz=constants.AwarePowerSettings.POWER_DW_24_NON_INTERACTIVE,
            dw_5ghz=constants.AwarePowerSettings.POWER_DW_5_NON_INTERACTIVE,
            num_iterations=100,
            csv_name="test_discovery_interactive_dws")
        asserts.explicit_pass(
            "test_discovery_latency_non_interactive_dws finished",
            extras=results)

    @ApiTest(
        apis=[
            'android.net.wifi.aware.WifiAwareManager#attach('
            'android.net.wifi.aware.AttachCallback,'
            'android.net.wifi.aware.IdentityChangedListener,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#publish('
            'android.net.wifi.aware.PublishConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareSession#subscrible('
            'android.net.wifi.aware.SubscribeConfig,'
            'android.net.wifi.aware.DiscoverySessionCallback,'
            'android.os.Handler)',
            'android.net.wifi.aware.WifiAwareNetworkSpecifier.Builder#build',
            'android.net.wifi.aware.WifiAwareSession#createNetworkSpecifierOpen(byte[])',
        ]
    )

    def test_discovery_latency_all_dws(self):
        """Measure the service discovery latency with all DW combinations (low
    iteration count)"""
        results = {}
        for dw24 in range(1, 6):  # permitted values: 1-5
            for dw5 in range(0, 6):  # permitted values: 0, 1-5
                self.run_discovery_latency(
                    results=results,
                    do_unsolicited_passive=True,
                    dw_24ghz=dw24,
                    dw_5ghz=dw5,
                    num_iterations=10,
                    csv_name="test_discovery_latency_all_dws")
        asserts.explicit_pass(
            "test_discovery_latency_all_dws finished", extras=results)



if __name__ == '__main__':
    # Take test args
    if '--' in sys.argv:
        index = sys.argv.index('--')
        sys.argv = sys.argv[:1] + sys.argv[index + 1:]

    test_runner.main()
