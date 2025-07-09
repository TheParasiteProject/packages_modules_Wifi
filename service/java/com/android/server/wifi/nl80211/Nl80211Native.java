/*
 * Copyright (C) 2025 The Android Open Source Project
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

package com.android.server.wifi.nl80211;

import android.annotation.NonNull;
import android.annotation.Nullable;
import android.os.Handler;
import android.util.Log;

import com.android.internal.annotations.VisibleForTesting;

import java.util.List;

/**
 * Provides functionalities that are implemented natively using Nl80211.
 */
public class Nl80211Native {
    private static final String TAG = "Nl80211Native";

    private final Nl80211Proxy mNl80211Proxy;
    private boolean mIsInitialized;

    public Nl80211Native(@NonNull Handler wifiHandler) {
        mNl80211Proxy = createNl80211Proxy(wifiHandler);
    }

    /**
     * Create an instance of Nl80211Proxy.
     * Intended to be overridden in the unit tests.
     */
    @VisibleForTesting
    protected Nl80211Proxy createNl80211Proxy(Handler wifiHandler) {
        return new Nl80211Proxy(wifiHandler);
    }

    /**
     * Initialize this instance of the class.
     *
     * @return true if successful, false otherwise.
     */
    public boolean initialize() {
        if (mIsInitialized) return true;
        mIsInitialized = mNl80211Proxy.initialize();
        Log.i(TAG, "Initialization status: " + mIsInitialized);
        return mIsInitialized;
    }

    /**
     * Check whether this instance has been initialized.
     */
    public boolean isInitialized() {
        return mIsInitialized;
    }

    /**
     * Get the names of all interfaces available on this device.
     *
     * @return List of interface names, or null if an error occurred.
     */
    public @Nullable List<String> getInterfaceNames() {
        if (!mIsInitialized) return null;
        return null;
    }
}
