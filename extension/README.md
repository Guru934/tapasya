# Tapasya Tab Reporter (Brave/Chromium, Manifest V3)

Reports the active tab's **domain, title, and whether the tab is producing sound** to the local daemon (127.0.0.1:8765).
No full URLs, page content, or audio data are collected, and incognito tabs are ignored. Pages like brave:// report an empty domain (not counted).

## Install (unpacked)
1. Open `brave://extensions`, turn on **Developer mode**.
2. Click **Load unpacked** and choose this `extension/` folder.
3. Make sure the tracker is running: `systemctl --user restart tapasya`.

## Check it works
```bash
curl -s http://127.0.0.1:8765/v1/status
sqlite3 ~/.local/share/tapasya/tapasya.db "select app_class,domain,counted from samples order by id desc limit 5;"
```
Open github.com (counts) then instagram.com (does not count) and compare. For YouTube, a regular
video title must contain a `study_keywords` value from `config.toml` (such as `lecture` or
`tutorial`); Shorts never count. Leave an audible lecture playing for longer than `idle_seconds`
without moving the mouse to verify that lecture playback keeps counting.
If a site you study on doesn't count, add it to `[study_sites] allow` in `config/config.toml`.
