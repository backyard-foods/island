# Local dev
- Install [Balena CLI](https://docs.balena.io/learn/getting-started/raspberrypi4-64/nodejs/)
- Turn on `Local mode` in the [Balena dashboard](https://dashboard.balena-cloud.com/devices)
- Run `sudo balena scan` to scan for devices
- Run `balena push <address>` to push to device and start [live reloads](https://docs.balena.io/learn/develop/local-mode/) 

# Pushing to fleet
- Get fleet name: `balena fleets`
- Push to fleet: `balena push <fleet-name>`

# Updating device Wi-Fi
1. SSH into Host OS
2. `cd /mnt/boot/system-connections/`
3. Open Wi-Fi config file with `vi <name>`
4. `i` to enter insert mode
5. Update SSID and PSK fields
6. `esc` to exit insert mode
7. `:wq` to save and exit
8. Restart device
