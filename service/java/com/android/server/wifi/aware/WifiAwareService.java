/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.android.server.wifi.aware;

import android.content.Context;
import android.net.wifi.WifiContext;
import android.os.HandlerThread;
import android.util.Log;

import com.android.server.SystemService;
import com.android.server.wifi.HalDeviceManager;
import com.android.server.wifi.WifiInjector;
import com.android.server.wifi.WifiNative;
import com.android.wifi.flags.FeatureFlags;

/**
 * Service implementing Wi-Fi Aware functionality. Delegates actual interface
 * implementation to WifiAwareServiceImpl.
 */
public final class WifiAwareService extends SystemService {
    private static final String TAG = "WifiAwareService";
    final WifiAwareServiceImpl mImpl;

    public WifiAwareService(Context contextBase) {
        super(new WifiContext(contextBase));
        mImpl = new WifiAwareServiceImpl(getContext());
    }

    @Override
    public void onStart() {
        Log.i(TAG, "Registering " + Context.WIFI_AWARE_SERVICE);
        publishBinderService(Context.WIFI_AWARE_SERVICE, mImpl);
    }

    @Override
    public void onBootPhase(int phase) {
        if (phase == SystemService.PHASE_SYSTEM_SERVICES_READY) {
            WifiInjector wifiInjector = WifiInjector.getInstance();
            if (wifiInjector == null) {
                Log.e(TAG, "onBootPhase(PHASE_SYSTEM_SERVICES_READY): NULL injector!");
                return;
            }

            HalDeviceManager halDeviceManager = wifiInjector.getHalDeviceManager();
            WifiNative wifiNative = wifiInjector.getWifiNative();
            FeatureFlags featureFlags = wifiInjector.getDeviceConfigFacade().getFeatureFlags();

            WifiAwareStateManager wifiAwareStateManager = new WifiAwareStateManager(wifiInjector,
                    new PairingConfigManager());
            WifiAwareNativeCallback wifiAwareNativeCallback = new WifiAwareNativeCallback(
                    wifiAwareStateManager);
            WifiAwareNativeManager wifiAwareNativeManager = new WifiAwareNativeManager(
                    wifiAwareStateManager, halDeviceManager, wifiAwareNativeCallback,
                    wifiNative, featureFlags);
            WifiAwareNativeApi wifiAwareNativeApi = new WifiAwareNativeApi(wifiAwareNativeManager);
            wifiAwareStateManager.setNative(wifiAwareNativeManager, wifiAwareNativeApi);
            WifiAwareShellCommand wifiAwareShellCommand = new WifiAwareShellCommand();
            wifiAwareShellCommand.register("native_api", wifiAwareNativeApi);
            wifiAwareShellCommand.register("native_cb", wifiAwareNativeCallback);
            wifiAwareShellCommand.register("state_mgr", wifiAwareStateManager);

            HandlerThread awareHandlerThread = wifiInjector.getWifiHandlerThread();
            mImpl.start(awareHandlerThread, wifiAwareStateManager, wifiAwareShellCommand,
                    wifiInjector.getWifiMetrics().getWifiAwareMetrics(),
                    wifiInjector.getWifiPermissionsUtil(),
                    wifiInjector.getWifiPermissionsWrapper(), wifiInjector.getSettingsConfigStore(),
                    wifiAwareNativeManager, wifiAwareNativeApi, wifiAwareNativeCallback,
                    wifiInjector.makeNetdWrapper(), wifiInjector.getInterfaceConflictManager());
        } else if (phase == SystemService.PHASE_BOOT_COMPLETED) {
            mImpl.startLate();
        }
    }
}

