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
import logging
import time

from mobly import asserts
from mobly.controllers import android_device


def set_screen_on_and_unlock(ad: android_device.AndroidDevice):
    """Sets the screen to stay on and unlocks the device.

    Args:
        ad: AndroidDevice instance.
    """
    ad.adb.shell("input keyevent KEYCODE_WAKEUP")
    ad.adb.shell("wm dismiss-keyguard")
    ad.adb.shell("svc power stayon true")

def enable_wifi_verbose_logging(ad: android_device.AndroidDevice):
    """Sets the Wi-Fi verbose logging developer option to Enable."""
    ad.adb.shell('cmd wifi set-verbose-logging enabled')

def take_bug_reports(ads, test_name=None, begin_time=None, destination=None):
    logging.info('Collecting bugreports...')
    android_device.take_bug_reports(ads, destination)

def restart_wifi_and_disable_connection_scan(ad: android_device.AndroidDevice):
    ad.wifi.wifiDisableAllSavedNetworks()
    ad.wifi.wifiDisable()
    ad.wifi.wifiEnable()
    ad.wifi.wifiAllowAutojoinGlobal(False)

def restore_wifi_auto_join(ad: android_device.AndroidDevice):
    ad.wifi.wifiEnableAllSavedNetworks()
    ad.wifi.wifiAllowAutojoinGlobal(True)

def skip_if_not_meet_min_sdk_level(
    ad: android_device.AndroidDevice, min_sdk_level: int
):
    """Skips current test if the Android SDK level does not meet requirement."""
    sdk_level = ad.build_info.get(
        android_device.BuildInfoConstants.BUILD_VERSION_SDK.build_info_key,
        None
    )
    asserts.skip_if(
        sdk_level is None, f'{ad}. Cannot get Android SDK level for device.'
    )
    sdk_level = int(sdk_level)
    asserts.skip_if(
        sdk_level < min_sdk_level,
        (
            f'{ad}. The sdk level {sdk_level} is less than required minimum '
            f'sdk level {min_sdk_level} for this test case.'
        ),
    )
