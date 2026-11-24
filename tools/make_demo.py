"""Generate the reference stereo signal using the standard library."""
from array import array
import math
from pathlib import Path
import wave

rate=48000
pcm=array('h')
for n in range(4*rate):
    t=n/rate
    left=right=0
    for start,duration,freq,channel in ((.4,.2,880,0),(.85,.2,880,0),(2.1,.65,440,1)):
        offset=t-start
        if 0 <= offset < duration:
            envelope=min(1,offset/.02,(duration-offset)/.02)
            value=round(2000*envelope*math.sin(2*math.pi*freq*offset))
            if channel==0:
                left=value
            else:
                right=value
    pcm.extend((left,right))
with wave.open(str(Path(__file__).resolve().parents[1]/'Test stereo.wav'),'wb') as f:
    f.setparams((2,2,rate,0,'NONE','not compressed'))
    f.writeframes(pcm.tobytes())
