#!/bin/bash
python Chunks.py | aplay --device=hw:0 -f S16_LE -r 48000 -c 2 -
