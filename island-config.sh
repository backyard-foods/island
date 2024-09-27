#!/bin/bash
if ! command -v balena &> /dev/null; then
    echo "Balena CLI is not installed. Please install it first."
    exit 1
fi

check_login() {
    if ! balena whoami &> /dev/null; then
        echo "You are not logged in. Please run 'balena login' first."
        exit 1
    fi
}

set_fleet_config() {
    check_login
    
    echo "Setting fleet-wide configuration for $FLEET_SLUG..."
    if balena env add BALENA_HOST_CONFIG_gpu_mem 128 --fleet $FLEET_SLUG && \
       balena env add BALENA_HOST_CONFIG_camera_auto_detect 1 --fleet $FLEET_SLUG && \
       balena env add BALENA_HOST_CONFIG_max_framebuffers 2 --fleet $FLEET_SLUG && \
       balena env add BALENA_HOST_CONFIG_dtoverlay '"w1-gpio,pullup=1","vc4-kms-v3d"'  --fleet $FLEET_SLUG && \
       balena env add BALENA_HOST_CONFIG_dtparam '"i2c_arm=on","spi=on","audio=on"' --fleet $FLEET_SLUG; then
        echo "Fleet configuration updated successfully for $FLEET_SLUG."
    else
        echo "Failed to update fleet configuration for $FLEET_SLUG."
        exit 1
    fi
}

case "$1" in
    dev)
        FLEET_SLUG="milan2/island-dev"
        set_fleet_config
        ;;
    prod)
        FLEET_SLUG="milan2/island-prod"
        set_fleet_config
        ;;
    *)
        echo "Usage: $0 {dev|prod}"
        exit 1
        ;;
esac
