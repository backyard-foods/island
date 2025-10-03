# Application containers:
- `island`: main flask server, manages comms with backend, temperature sensors (TODO: move to separate container)
- `porchlight`: manages lights over GPIO
- `wave`: manages music
- `label-printer`: manages chit printer
- `receipt-printer`: manages customer receipt printer
- `baywatch`: manages security camera
- `reaper`: manages daily reboots and reboots in case of connectivity failures

# Local dev
- Install [Balena CLI](https://docs.balena.io/learn/getting-started/raspberrypi4-64/nodejs/)
- Turn on `Local mode` in the [Balena dashboard](https://dashboard.balena-cloud.com/devices)
- Run `sudo balena scan` to scan for devices
- Run `balena push <address>` to push to device and start [live reloads](https://docs.balena.io/learn/develop/local-mode/) 
- Define local env vars in `docker-compose.yml`
- Start `byf-api` locally (`supabase start` then `supabase functions serve`), update `ISLAND_IP` in `<byf-api>/supabase/functions/.env` and `BYF_API_URL` in `<oasis-island>/docker-compose.yml`
- Start `oasis-island` locally

# Pushing to fleet
- Get fleet name: `balena fleets`
- Push to fleet: `balena push <fleet-name>`
- Define env vars in balena console at fleet and/or device level
- Update configuration in `island-config.sh` and run `zsh island-config.sh <dev|prod>` to set fleet-wide configuration

# Updating device Wi-Fi
1. SSH into Host OS
2. `cd /mnt/boot/system-connections/`
3. Open Wi-Fi config file with `vi <name>`
4. `i` to enter insert mode
5. Update SSID and PSK fields
6. `esc` to exit insert mode
7. `:wq` to save and exit
8. Restart device

# SSH when running in Local Mode
- Host OS: `balena ssh <device-IP-address>`
- Container: `sudo balena ssh <device-IP-address> <container-name>`

# ADB from Reaper
- TODO: figure out how to use standardized keys that persist between builds so we don't have to keep re-authing with the kiosk tablet