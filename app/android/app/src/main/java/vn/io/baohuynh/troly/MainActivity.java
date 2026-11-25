package vn.io.baohuynh.troly;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

import vn.io.baohuynh.troly.plugin.AlarmPlugin;
import vn.io.baohuynh.troly.plugin.FilesPlugin;
import vn.io.baohuynh.troly.plugin.MapsPlugin;
import vn.io.baohuynh.troly.plugin.NotifyPlugin;
import vn.io.baohuynh.troly.plugin.SecurePlugin;
import vn.io.baohuynh.troly.plugin.ShareInPlugin;
import vn.io.baohuynh.troly.plugin.SystemPlugin;
import vn.io.baohuynh.troly.plugin.UpdatePlugin;
import vn.io.baohuynh.troly.plugin.VoicePlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Plugin cục bộ của app phải đăng ký trước super.onCreate (30-app-android.md mục 3.3).
        registerPlugin(SecurePlugin.class);
        registerPlugin(NotifyPlugin.class);
        registerPlugin(SystemPlugin.class);
        registerPlugin(AlarmPlugin.class);
        registerPlugin(MapsPlugin.class);
        registerPlugin(FilesPlugin.class);
        registerPlugin(VoicePlugin.class);
        registerPlugin(ShareInPlugin.class);
        registerPlugin(UpdatePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
