#!/bin/bash
sudo alsactl  --file ./asound.state restore audioinjectorpi
arecord -f S32 -c2 -r48000 -t raw --device=hw:3,0 - |  od -x
