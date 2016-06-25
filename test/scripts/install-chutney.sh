#!/bin/bash
# Script to install Chutney, configure a Tor network and export
# an environment variable CHUTNEY_CONTROL_PORT
git clone https://git.torproject.org/chutney.git
cd chutney
# Stop chutney network if it is already running
./chutney stop networks/basic-025
./chutney configure networks/basic-025
./chutney start networks/basic-025
./chutney status networks/basic-025

# Retry verify until hidden service subsystem is working
client_torrc=$(find net/nodes -wholename "*c/torrc" | head -n1)
control_port=$(grep -Po -m1 "ControlPort\s(\d+)$" $client_torrc | awk '{print $2}')
export CHUTNEY_CONTROL_PORT="$control_port"
# How do we know when all has settled?
sleep 15
cd ..
