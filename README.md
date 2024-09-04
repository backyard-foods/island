# Local dev
- Install [Balena CLI](https://docs.balena.io/learn/getting-started/raspberrypi4-64/nodejs/)
- Turn on `Local mode` in the [Balena dashboard](https://dashboard.balena-cloud.com/devices)
- Run `balena scan` to scan for devices
- Run `balena push <address>` to push to device and start [live reloads](https://docs.balena.io/learn/develop/local-mode/) 

# Pushing to fleet
- Get fleet name: `balena fleets`
- Push to fleet: `balena push <fleet-name>`