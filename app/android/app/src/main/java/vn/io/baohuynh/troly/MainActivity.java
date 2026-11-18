package vn.io.baohuynh.troly;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

import vn.io.baohuynh.troly.plugin.AlarmPlugin;
import vn.io.baohuynh.troly.plugin.NotifyPlugin;
import vn.io.baohuynh.troly.plugin.SecurePlugin;
import vn.io.baohuynh.troly.plugin.SystemPlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Plugin cục bộ của app phải đăng ký trước super.onCreate (30-app-android.md mục 3.3).
        registerPlugin(SecurePlugin.class);
        registerPlugin(NotifyPlugin.class);
        registerPlugin(SystemPlugin.class);
        registerPlugin(AlarmPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
