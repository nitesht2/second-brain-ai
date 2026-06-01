# Mac capture bridge

Pushes new files in the Mac vault `~/SecondBrain/raw/` up to the VPS so the
agent ingests them. Lets the Obsidian Web Clipper (Chrome) feed the VPS brain:

  click clipper -> Obsidian (running) writes .md to ~/SecondBrain/raw/
    -> mac_push_watcher.sh (fswatch) -> scp to VPS raw/ -> agent ingests

## Setup
1. `brew install fswatch`
2. Edit `mac_push_watcher.sh`: set `BRAIN_VPS_HOST` (or hardcode root@<vps-ip>).
   Passwordless SSH key to the VPS required.
3. Copy plist to `~/Library/LaunchAgents/com.secondbrain.macpush.plist`
   (fix the absolute paths), then:
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.secondbrain.macpush.plist`
4. In Obsidian Web Clipper settings, set the save folder to `~/SecondBrain/raw/`.
5. Set Obsidian to launch at login (System Settings > Login Items) so the
   clipper always has a target.
