# Version 5-16-2017 
import wave
import os
import sys
import signal
import time
import datetime
import numpy as np
from scipy.fftpack import rfft, fft
import socket

## c.f. https://docs.python.org/2/library/subprocess.html
##  POSIX users (Linux, BSD, etc.) are strongly encouraged to install and use
##  the much more recent subprocess32 module instead of the version included
##  with python 2.7. It is a drop in replacement with better behavior in many
##  situations.
## See Usage at https://github.com/google/python-subprocess32:
#
#if os.name == 'posix' and sys.version_info[0] < 3:
#    import subprocess32 as subprocess
#else:
#    import subprocess
#
#MCAST_GRP = '224.0.0.224'
#MCAST_PORT = 5007

ReadMore = True

def handler(signum, frame):
    global ReadMore
    print ('Signal handler called with signal', signum )
    ReadMore = False

Offset = -147.7
Arr_Range = np.array([[],[]],dtype=np.int32)
#One_3rd_Power = np.zeros(33)
Power_Int = 0
OTP = np.zeros(33)
OTP = np.zeros(33)
OTA = np.zeros(33)
OTC = np.zeros(33)
OTF = np.zeros(33)

def now():
    return time.time()

#
#  A, C and Flat corrections to Log Power 1/3 Octave data
#
Alaw = np.array( [-63.4, -56.7, -50.5, -44.7, -39.4,\
               -34.6, -30.2, -26.2, -22.5, -19.1,\
                -16.1, -13.4, -10.9, -8.6, -6.6,\
                -4.8, -3.2, -1.9, -0.8, 0,\
                0.6, 1, 1.2, 1.3, 1.2,\
                1, 0.5, -0.1, -1.1, -2.5,\
                -4.3, -6.6, -9.3])
Claw = np.array([-11.2, -8.5, -6.2, -4.4, -3, -2, \
               -1.3, -0.8, -0.5, -0.3, -0.2, -0.1, \
               0, 0, 0, 0, 0, 0, \
               0, 0, 0, -0.1, -0.2, -0.3, \
              -0.5, -0.8, -1.3, -2, -3, -4.4, \
              -6.2, -8.5, -11.2] )
Flat = np.array([-4.2, -2.9, -1.9, -1.3, -0.8, -0.5, \
               -0.3, -0.2, -0.1, -0.1, 0, 0, \
               0, 0, 0, 0, 0, 0, \
               0, 0, 0, 0, 0, 0, \
               0, 0, 0, 0, 0, 0, \
               0, 0, 0])
#

def Calc_One_Third (Arr_Range) :

    t_samp = 1/48000.0
    N = 48000
    
    One_Third = np.array([[11.2,12.5,14.1],  [14.1,16,17.8],   [17.8,20,22.4], 
                    [22.4,25,28.2],      [28.2,31.5,35.5], [35.5,40,44.7], 
                    [44.7,50,56.2],      [56.2,63,70.8], [70.8,80,89.1], 
                    [89.1,100,112],      [112,125,141], [141,160,178], 
                    [178,200,224],       [224,250,282], [282,315,355],
                    [355,400,447],       [447,500,562], [562,630,708], 
                    [708,800,891],      [891,1000,1122], [1122,1250,1413], 
                  [1413,1600,1778],    [1778,2000,2239], [2239,2500,2818], 
                  [2818,3150,3548],    [3548,4000,4467], [4467,5000,5623], 
                  [5623,6300,7079],    [7079,8000,8913], [8913,10000,11220], 
                 [11220,12500,14130],[14130,16000,17780], [17780,20000,22390]])
    Freqs = np.fft.fftfreq(N,t_samp)
    #print(Freqs)
    Index_High = 0
    Index_Low = 0
    Temp = np.empty([1,2],dtype=np.int32)
    #print(Arr_Range)
    #print(Temp)
    i = 0
    for j in np.arange(0,len(One_Third)) : 
        #print(j,One_Third[j,0],One_Third[j,1],One_Third[j,2])
        Repeat = True
        while Repeat :
            if (One_Third[j,0] >=  Freqs[i]) :
                Index_Low = i 
            if (Freqs[i] > One_Third[j,0]) and (Freqs[i] <= One_Third[j,2]) :
                Index_High = i
            if (Freqs[i] > One_Third[j,2]) :
                Repeat = False
            i = i + 1
        #print(j,Index_Low,Index_High)
        Temp = [[Index_Low],[Index_High]]
        Index_Low = Index_High 
        #print(j,Temp)
        Arr_Range = np.append(Arr_Range,Temp)
        Temp = np.empty([1,2],dtype=np.int32)
    Arr_Range = np.reshape(Arr_Range,(len(One_Third),2))
    #for j in np.arange(0,len(One_Third)) :
        #print(j,One_Third[j,0],One_Third[j,1],One_Third[j,2], Arr_Range[j,:])
        #print(j,Arr_Range[j,:])
    #print(Arr_Range)
    return Arr_Range

## Set up UDP Sockets
#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
#sock.setblocking(0)
##
Arr_Range = Calc_One_Third(Arr_Range)
#print "Returned: ", Arr_Range
Num_BytesPerMinute = 48000 * 4
Bytes2Read = Num_BytesPerMinute
Writeless = 0
FileNum = 0
TotalRead = 0
SiteID = socket.gethostname()
#
#  Signal handler instantiation
#
signal.signal(signal.SIGTERM, handler)
#signal.signal(signal.SIGINT, handler)

#
#  New code to generate prefix date, Tim start, Time end string
#
t_str = time.strftime("%Y-%m-%d %H:%M:%S")
date = time.strftime('%Y-%m-%d ')
date_old = date
datetime_object = datetime.datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
time_string = '{:%H:%M:%S}'.format(datetime_object)
###
old_minute = datetime.datetime.utcfromtimestamp(now()).minute
timestr = time.strftime("%Y%m%d-%H%M%S")
win = np.blackman(48000)
y = np.array([], dtype='i4')
n = 0
x = np.array([], dtype='i4')

wdB_name = '/home/pi/Audio/'+SiteID+'-'+timestr+'.csv'
wdB = os.open(wdB_name,os.O_RDWR|os.O_CREAT)
while ReadMore :
    if Writeless == 0 :
        wf_name = '/home/pi/Audio/'+SiteID+'-'+timestr+'.wav'
        wf = wave.open(wf_name, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(4)
        wf.setframerate(48000)
#       x = np.array([], dtype='i4')
    #print "trying to read"
    buf = os.read(0,6000)
    #buf = wavin.stdout.read(6000)
    #print len(buf)
    TotalRead = TotalRead + len(buf)
    if len(buf) != 0 :
       #os.write(wf,buf)
       wf.writeframes(buf)
       xlen = len(x)
       y =np.frombuffer(buf,dtype=np.int32)
       ylen = len(y)
       if ( (xlen + ylen) <= 48000) :
           x = np.append(x,y)
           #print(xlen,ylen)
           y_left = np.array([],dtype='i4')
       else :
           xfer_cnt = 48000 - len(x)
           #print(xlen,ylen,xfer_cnt)
           y_left = np.delete(y,np.arange(0,xfer_cnt,1))
           y = np.delete(y,np.arange(xfer_cnt,ylen,1))
           x = np.append(x,y)
           #print("Now: ",len(x), len(y), len(y_left))
    else :
        time.sleep(0.125)
    Writeless = Writeless + len(buf)
    seconds= datetime.datetime.utcfromtimestamp(now()).second
    minutes = datetime.datetime.utcfromtimestamp(now()).minute
    if (len(x) >= 48000) :
        timestr = time.strftime("%Y%m%d-%H%M%S")
        x = np.multiply(x,win)
        X = np.abs(np.fft.fft(x))
        for i in np.arange(0,len(Arr_Range)) :
               ilow = Arr_Range[i,0]
               ihigh = Arr_Range[i,1]
               OTP[i] =Offset + 10*np.log10( np.sum(X[ilow:ihigh]**2) )
               OTC[i] = OTP[i] + Claw[i]
               OTA[i] = OTP[i] + Alaw[i]
               OTF[i] = OTP[i] + Flat[i]
        PowerA = 0.0
        PowerFlat = 0.0
        PowerC = 0.0
        for i in np.arange(0,len(Arr_Range)) :
               PowerA = PowerA + np.power(10,OTA[i]/10.0)
               PowerC = PowerC + np.power(10,OTC[i]/10.0)
               PowerFlat = PowerFlat + np.power(10,OTF[i]/10.0)
        Power_Int = Power_Int+1
        dBlogA = 10*np.log10(PowerA)
        dBlogC = 10*np.log10(PowerC)
        dBlogFlat = 10*np.log10(PowerFlat)
######
#
#  Format the 1/3 dB spectra as Gonzalo wants it
#
#####
#       time_string_new = '{:%H:%M:%S}'.format(datetime_object + datetime.timedelta(0,Power_Int))
        time_string_new = time.strftime("%H:%M:%S")
        Str_To_Print = SiteID + ',' + date + time_string + ',' + time_string_new
        time_string = time_string_new
#        print '{0:s},{1:5.1f},{2:5.1f},{3:5.1f},\
        p_string = '{0:s},{1:5.1f},{2:5.1f},{3:5.1f},\
{4:5.1f},{5:5.1f},{6:5.1f},{7:5.1f},\
{8:5.1f},{9:5.1f},{10:5.1f},{11:5.1f},\
{12:5.1f},{13:5.1f},{14:5.1f},{15:5.1f},\
{16:5.1f},{17:5.1f},{18:5.1f},{19:5.1f},\
{20:5.1f},{21:5.1f},{22:5.1f},{23:5.1f},\
{24:5.1f},{25:5.1f},{26:5.1f},{27:5.1f},\
{28:5.1f},{29:5.1f},{30:5.1f},{31:5.1f},\
{32:5.1f},{33:5.1f},{34:5.1f},{35:5.1f},\
{36:5.1f},,,,,,,,,,,,,,,,' .format(Str_To_Print, OTP[0],OTP[1],OTP[2],\
OTP[3],OTP[4],OTP[5],OTP[6],\
OTP[7],OTP[8],OTP[9],OTP[10],
OTP[11],OTP[12],OTP[13],OTP[14],\
OTP[15],OTP[16],OTP[17],OTP[18],\
OTP[19],OTP[20],OTP[21],OTP[22],\
OTP[23],OTP[24],OTP[25],OTP[26],\
OTP[27],OTP[28],OTP[29],OTP[30],\
OTP[31],OTP[32],dBlogA,dBlogC,dBlogFlat)
        #print p_string
        #sock.sendto(p_string, (MCAST_GRP, MCAST_PORT))
        s2write = p_string + '\n'
        array_2_write = s2write.encode('ascii')
        #os.write(wdB,s2write)
        os.write(wdB,array_2_write)
        #print One_3rd_Power
        x = y_left
        n = n + 1
    if ( ( seconds == 0 ) & (old_minute != minutes ) ) :
        wf.close
        if (Writeless < 45) or (len(buf) ==0 ) :
		#print "No Data Read from STDIN"
            ReadMore = False
        timestr = time.strftime("%Y%m%d-%H%M%S")
        Writeless = 0
        #print "Closed .wav file ", wf_name
        #print("time at top of the minute: {0:d}".format(minutes))
        old_minute = minutes
        date = time.strftime('%Y-%m-%d ')
        if ( date != date_old ) :
            os.close(wdB)
            wdB_name = '/media/usb0/AUDIO/'+SiteID+'-'+timestr+'.csv'
            wdB = os.open(wdB_name,os.O_RDWR|os.O_CREAT)
            date_old = date
os.close(wdB)
wf.close
print ("Exiting the Program")
