#!/bin/bash

# Install required dependencies with specific versions
sudo apt-get update
sudo apt-get install -y \
    libasound2=1.2.4-* \
    alsa-utils=1.2.4-* \
    libpulse0=14.2-* \
    systemd=247.3-*

# Install the downloaded package
sudo dpkg -i /tmp/raspotify.deb

# Install any remaining missing dependencies
sudo apt-get install -f

# Clean up the downloaded file
rm /tmp/raspotify.deb
