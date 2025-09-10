import sys
import os
import numpy as np
import math
def write_raw_stdout(data: bytes, buffer_size: int = 4096):
    """Writes raw byte data to stdout, handling buffering and potential overruns.

    Args:
        data: The byte data to write.
        buffer_size: The maximum buffer size in bytes.
    """
    data_len = len(data)
    offset = 0

    while offset < data_len:
        chunk_size = min(buffer_size, data_len - offset)
        
        try:
            os.write(sys.stdout.fileno(), data[offset:offset + chunk_size])
        except BlockingIOError:
            # Handle the case where stdout is temporarily unavailable
            # In real-world scenarios, you might want to implement more sophisticated retry logic
            print("stdout buffer full, waiting...")
            time.sleep(0.1)
            continue
            
        offset += chunk_size

if __name__ == '__main__':
    # Example usage:
    sr = 48000  # DAC Audio Sample rate
    freq = 240.0  # 44o Hertz
    buff_len = 480
    sample_len = int( buff_len / 2  )
    Volume = 8000
    t_idx = 0
    dat_array = np.zeros(buff_len,dtype=np.int16)  # 0.1 second array
    while True :
        index = 0
        for i in range(sample_len)  : 
            sample = Volume * math.sin(2*math.pi*(float(t_idx*freq)/float(sr)))
            dat_array[index] = sample
            dat_array[index + 1] =  sample
            index = index + 2
            t_idx = t_idx +1
        write_raw_stdout(dat_array)
        if t_idx > 100000 :
            exit()
     
#    write_raw_stdout(data_to_write)
