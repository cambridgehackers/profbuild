#!/bin/bash -x

[ -d sandbox ] || mkdir sandbox
sudo rm -rf sandbox/bb*
sudo mount -t tmpfs bozo_unused sandbox
