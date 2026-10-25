#!/bin/sh
set -eu
export N3_ADDRESS="$(ip -4 -o addr show "${N3_INTERFACE:-net1}" | awk '{print $4}' | cut -d/ -f1)"
test -n "$N3_ADDRESS"
exec /usr/local/bin/ue-phones
