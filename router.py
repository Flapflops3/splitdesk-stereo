"""Route left to a Moonlight client and right to local speakers."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import argparse
import json
import logging
from pathlib import Path
import sys
import threading
import time

sys.coinit_flags = 0  # SoundCard initializes the multithreaded COM apartment.
import soundcard  # SoundCard must establish COM before pycaw on the capture thread.
from pycaw.constants import ERole
from pycaw.pycaw import AudioUtilities

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'previous-output.json'
STOP = ROOT / 'stop.request'
CONFIG = json.loads((ROOT / 'routing.json').read_text(encoding='utf-8-sig'))
SOURCE = CONFIG['desktop_mix']
REMOTE = CONFIG['remote_output']
LOCAL = CONFIG['local_output']
ROLES = [ERole.eConsole, ERole.eMultimedia]  # Communications devices stay user-selected.
RATE = 48000
CHUNK = 480
logging.basicConfig(filename=ROOT/'routing.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

def current(role):
    return AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(0, role.value).GetId()

def restore():
    if not STATE.exists():
        return
    previous = json.loads(STATE.read_text())
    for role in ROLES:
        if current(role).lower() == SOURCE.lower():
            try:
                AudioUtilities.SetDefaultDevice(previous[role.name], [role])
            except OSError:
                AudioUtilities.SetDefaultDevice(LOCAL, [role])
    STATE.unlink(missing_ok=True)

def begin():
    restore()
    previous = {role.name: current(role) for role in ROLES}
    # If another streaming session left its virtual speakers active, restore the laptop.
    previous = {k: LOCAL if v.lower() in {SOURCE.lower(), REMOTE.lower()} else v for k,v in previous.items()}
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(previous))
    os.replace(temp, STATE)
    AudioUtilities.SetDefaultDevice(SOURCE, ROLES)

def output_index(endpoint_id):
    import soundcard as sc
    import sounddevice as sd
    name = sc.get_speaker(endpoint_id).name
    wasapi = next(i for i, api in enumerate(sd.query_hostapis()) if api['name']=='Windows WASAPI')
    matches = [i for i,d in enumerate(sd.query_devices())
               if d['hostapi']==wasapi and d['name']==name and d['max_output_channels']>=2]
    if len(matches)!=1:
        raise RuntimeError(f'Expected one WASAPI output named {name!r}, found {len(matches)}')
    return matches[0]

class StereoBuffer:
    """Each output follows the capture clock with a small independent rate correction."""
    def __init__(self):
        import numpy as np
        self.np = np
        self.frames = np.zeros((RATE, 2), dtype=np.float32)
        self.written = 0
        self.lock = threading.Lock()
        self.last_callback = [time.monotonic(), time.monotonic()]

    def append(self, block):
        with self.lock:
            positions = (self.written + self.np.arange(len(block))) % len(self.frames)
            self.frames[positions] = block
            self.written += len(block)

    def callback(self, channel, delay_ms):
        np = self.np
        target = int(RATE*(0.04 + delay_ms/1000))
        position = None
        def render(out, count, timing, status):
            nonlocal position
            self.last_callback[channel] = time.monotonic()
            out.fill(0)
            with self.lock:
                if self.written < target + count:
                    return
                if position is None or self.written-position > target+RATE//5:
                    position = self.written-target
                buffered = self.written-position
                step = np.clip(1+(buffered-target)/(RATE*8), 0.997, 1.003)
                indices = position + step*np.arange(count)
                if indices[-1]+1 >= self.written:
                    position = None
                    return
                base = indices.astype(np.int64)
                fraction = indices-base
                a = self.frames[base % RATE,channel]
                b = self.frames[(base+1) % RATE,channel]
                mono = a+(b-a)*fraction
                position += step*count
            out[:,0] = mono
            out[:,1] = mono
        return render

def run_audio():
    import soundcard as sc
    import sounddevice as sd
    from audio_tone import LiveEQ
    tone = LiveEQ()
    buffer = StereoBuffer()
    recording = sc.get_microphone(CONFIG['cable_recording'], include_loopback=False)
    if recording.isloopback or 'VB-Audio Virtual Cable' not in recording.name:
        raise RuntimeError('Expected the VB-CABLE recording endpoint')
    def stream(endpoint, channel, delay):
        return sd.OutputStream(device=output_index(endpoint), samplerate=RATE, channels=2,
                               dtype='float32',blocksize=CHUNK,latency='low',
                               callback=buffer.callback(channel,delay))
    delay = float(CONFIG['local_delay_ms'])
    if not 0 <= delay <= 300:
        raise ValueError('local_delay_ms must be between 0 and 300')
    with recording.recorder(RATE, channels=2, blocksize=CHUNK) as rec, \
         stream(REMOTE, 0, 0) as left, stream(LOCAL, 1, delay) as right:
        begin()
        logging.info("Split stereo active")
        while not STOP.exists():
            buffer.append(tone.process(rec.record(CHUNK)))
            if not left.active or not right.active or time.monotonic()-min(buffer.last_callback)>2:
                raise RuntimeError("An output stopped. Check the endpoints and start the route again.")


def lock_route():
    import msvcrt
    handle = (ROOT/'route.lock').open('a+b')
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def stop():
    STOP.touch()
    for _ in range(100):
        guard = lock_route()
        if guard:
            with guard:
                restore()
            return
        time.sleep(.1)
    raise RuntimeError("The router did not stop. See routing.log.")


def check():
    import sounddevice as sd
    import soundcard as sc
    if len({SOURCE,REMOTE,LOCAL})!=3:
        raise ValueError("Three different render endpoints are required.")
    for endpoint in (SOURCE,REMOTE,LOCAL):
        sd.check_output_settings(device=output_index(endpoint),channels=2,dtype='float32',samplerate=RATE)
        print(sc.get_speaker(endpoint).name)
    mic=sc.get_microphone(CONFIG['cable_recording'],include_loopback=False)
    if mic.isloopback or 'vb-audio virtual cable' not in mic.name.lower():
        raise RuntimeError("Select the VB-CABLE recording endpoint.")
    print("Recording endpoint:",mic.name)
    print("48 kHz stereo output checks passed.")


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['start','stop','check'])
    mode=parser.parse_args().mode
    try:
        if mode=='check':
            check()
        elif mode=='stop':
            stop()
        else:
            guard=lock_route()
            if guard:
                with guard:
                    STOP.unlink(missing_ok=True)
                    restore()
                    try:
                        run_audio()
                    finally:
                        restore()
                        logging.info("Split route closed")
    except Exception:
        logging.exception("Audio routing failed")
        raise
