#!/bin/bash
sudo alsactl  --file ~/.config/asound.state restore audioinjectorpi
arecord -f S32 -c2 -r48000 -t wav --device=hw:3,0 - |  aplay
