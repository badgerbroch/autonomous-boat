#!/bin/bash
python Chunks_short.py | sox -r 48k -e signed -b 16 -c 2 -t raw - -t wav out_short.wav
