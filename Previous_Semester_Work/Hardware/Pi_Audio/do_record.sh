#!/bin/bash
sudo alsactl  --file ./asound.state restore audioinjectorpi
arecord --device=hw:3,0 -f S32 -c2 -r48000 -t wav  $1
