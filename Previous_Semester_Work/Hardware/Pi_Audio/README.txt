This file contains the Python executable for the Sound Level Meter Program
 and some useful scripts to test that the system is operatonal.
Python code in this directory is installed in a Virtual Environment Directory.
To active the virtual environment tye this from the command line:
    pi@pi4Bbasic:~/Source/Pi_Audio $ source venv_act.sh 
To deactivate the virtual environment type this from the command line:
     (Venv) pi@pi4Bbasic:~/Source/Pi_Audio $ source venv_deact.sh  

To start the process, use "alsamixer" to set up the audioinjector sound card the
way you want to. Then use "alsactrl" to save the state:
     pi@pi4Bbasic:~/Source/Pi_Audio $ sudo alsactl store -f ./asound.state

Here are the files and their meaning:

asound.state    : Current alsa controls state
do_record.sh    : records audio from audioinjectorpi to <filename.wav>
                : Invoke it with ./do_record.sh <filename.wav>
                : Use <ctrl>c to stop the file recordngng
do_SLM.sh       : Complex script to execute the SLM Program.  It uses 
                : arecord, sox, and delay plus the Python Program 
                :    RCW_wavACFlat_Soc_Sig.py
                : it records 1 minute wav audio files to ~/Audio
                : along with a .csv formatted sound level data.
do_test.sh      : connects audioinjector "in" to "out" for testing
RCW_wavACFlat_Soc_Sig.py  : see "do_SLM.sh" above
README.txt      : this file
Read_pipe_to_od.sh  : reads the audio channels and uses "octal dump" t show data
                : Use <ctrl>c to sti it.
Venv            : Virtual environment build directory
venv_act.sh     : type:  source ./venv_act.sh   to activate the VENV
venv_deact.sh   : type:  source ./venv_deact.sh   to deactivate the VENV
