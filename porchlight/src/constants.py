# format- "device-name": "device-address"
devices = {
    "test": "C7:6A:05:46:35:6C"
}
device_names = list(devices.keys())
addr_dev_dict = {v:k for k,v in devices.items()}
handle = 21
handle_hex = "0x{:04x}".format(handle)
server_secret = ""
server_port = 5000
