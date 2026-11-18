package vn.io.baohuynh.troly;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

import vn.io.baohuynh.troly.secure.SecurePlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Plugin cục bộ của app phải đăng ký trước super.onCreate (30-app-android.md mục 3.3).
        registerPlugin(SecurePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
