#!/bin/bash
python Chunks.py | aplay --device=hw:3 -f S16_LE -r 48000 -c 2 -
