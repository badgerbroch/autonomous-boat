This directory has Python programs that generate a sine wave audio data and
helper scripts to either play them on the audio card or save them as a file.
The prgram was built in a Virtual Environment into the directory Venv.  
See the files for the Pi_Audio on how to setup the Audioinjectorpi card
for use here.  Omnce it is configured, use "sudo aslactl save -f <filename>"
  for saving the configuration.  Use "alsamixer" to set it up.

It is assumed that the audio Headphones jack on the Pi is Device 0 and the
AUdioinjector Card is Device 3.

Here are the specific files and descriptions:

Chunks.py           : A program that generates S16_LE stereo data in raw fromat
                    : Use <ctrl>c to stp the prgram
                    : It writes stdout and is normally piped to aplay
Chunks_short.py     : A program that generates a limited sequence of S16_LE sine data
do_chunks_2_wav.sh  : A helper script that generates a short .wav audio file of sine
                    : data to the file named out_short.wav 
                    : Note: it uses "sox" t format the audio data
do_play0.sh         : A helper script that invokes Chunks.py and plays it on card 0
do_play3.sh         : A helper script that invokes Chunks.py and plays it on card 3
out_short.wav       : An audio file created by do_chunks_2_wav.sh
README.txt          : This file
Venv                : the Venv Build (not included in the zip file)
