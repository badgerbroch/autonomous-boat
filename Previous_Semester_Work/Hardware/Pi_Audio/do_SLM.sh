#!/bin/bash
sudo alsactl  --file ./asound.state restore audioinjectorpi
arecord -f S32 -c2 -r48000 -t raw --device=hw:3,0 - | \
sox -r 48k -e signed -b 32 -c 2 -t raw -  -t raw  -r 48k -e signed - remix 1  \
 | delay -b2m | python ./RCW_wavACFlat_Soc_Sig.py
