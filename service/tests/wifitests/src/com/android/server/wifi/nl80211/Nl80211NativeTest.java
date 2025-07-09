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

import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.when;

import android.os.Handler;

import org.junit.Before;
import org.junit.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

/**
 * Unit tests for {@link Nl80211Native}.
 */
public class Nl80211NativeTest {
    private TestNl80211Native mDut;

    @Mock Handler mHandler;
    @Mock Nl80211Proxy mNl80211Proxy;

    // Extended class allows us to use a mock instance of Nl80211Proxy.
    private class TestNl80211Native extends Nl80211Native {
        TestNl80211Native() {
            super(mHandler);
        }

        @Override
        protected Nl80211Proxy createNl80211Proxy(Handler wifiHandler) {
            return mNl80211Proxy;
        }
    }

    @Before
    public void setUp() throws Exception {
        MockitoAnnotations.initMocks(this);
        mDut = new TestNl80211Native();
        when(mNl80211Proxy.initialize()).thenReturn(true);
        assertTrue(mDut.initialize());
        assertTrue(mDut.isInitialized());
    }

    /**
     * Test that {@link Nl80211Native#getInterfaceNames()} returns the expected value.
     */
    @Test
    public void testGetInterfaceNames() {
        assertNull(mDut.getInterfaceNames());
    }
}
