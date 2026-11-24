"""Read timestamped local audio tracks and mix them to the current Windows output."""
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Thread
import time
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_tone import LiveEQ

MIX_ENDPOINT = json.loads((ROOT / 'routing.json').read_text(encoding='utf-8-sig'))['desktop_mix']

import comtypes
import numpy as np
import sounddevice as sd
from pycaw.pycaw import AudioUtilities

RATE = 48000
BLOCK = 960
LABELS = {'FL':'Front left','FR':'Front right','FC':'Center','LFE':'LFE','SL':'Side left',
          'SR':'Side right','BL':'Back left','BR':'Back right','BC':'Back center'}
STEMS = ('vocals','vocal','instrumental','accompaniment','bass','drums','guitar',
         'piano','人声','伴奏','鼓','贝斯','吉他','钢琴')

@dataclass(frozen=True)
class Track:
    name: str
    detail: str
    stream: int
    matrix: np.ndarray
    enabled: bool

@dataclass(frozen=True)
class Source:
    path: Path
    index: int
    layout: str
    origin: float
    channels: int

@dataclass
class Project:
    sources: list
    tracks: list
    duration: float
    title: str

def channel_mix(names):
    if len(names)==1:
        return np.ones((1,2),np.float32)
    if len(names)==2:
        return np.eye(2,dtype=np.float32)
    gains=[]
    for name in names:
        if name in ('FL','FR'):
            gains.append((1,0) if name=='FL' else (0,1))
        elif name.endswith('L'):
            gains.append((.707,0))
        elif name.endswith('R'):
            gains.append((0,.707))
        else:
            g=.35 if name.startswith('LFE') else .707
            gains.append((g,g))
    # Headroom for summing a surround bed onto two speakers.
    matrix=np.array(gains,np.float32)
    return matrix / max(1.,float(matrix.sum(axis=0).max()))

def stem_names(path):
    # NI stores four stem labels in the MP4 moov/udta/stem box.
    with path.open('rb') as f:
        start,end=0,path.stat().st_size
        for target in (b'moov',b'udta',b'stem'):
            while start+8<=end:
                f.seek(start)
                size,kind=struct.unpack('>I4s',f.read(8))
                if size==1:
                    extended=f.read(8)
                    if len(extended)!=8:
                        return []
                    size=int.from_bytes(extended,'big')
                stop=start+size if size else end
                if stop<f.tell() or stop>end:
                    return []
                if kind==target:
                    start,end=f.tell(),stop
                    break
                start=stop
            else:
                return []
        if end-start>1024*1024:
            return []
        raw=f.read(end-start).strip(b'\\x00 \\n\\r\\t')
        try:
            meta=json.loads(raw)
        except (UnicodeError,ValueError):
            return []
        entries=meta.get('stems') if isinstance(meta,dict) else None
        if not isinstance(entries,list) or len(entries)!=4:
            return []
        return [item.get('name','') if isinstance(item,dict) and isinstance(item.get('name'),str)
                else '' for item in entries]

def inspect_files(paths):
    import av
    sources,tracks=[],[]
    end=0.
    for path in map(Path,paths):
        with av.open(str(path)) as media:
            streams=list(media.streams.audio)
            if not streams:
                raise ValueError(f'No playable audio tracks in {path.name}')
            origin=(media.start_time or 0)/av.time_base
            end=max(end,(media.duration or 0)/av.time_base)
            titles=[s.metadata.get('title') or s.metadata.get('handler_name','') for s in streams]
            ni_labels=stem_names(path) if len(streams)==5 and path.suffix.lower() in ('.mp4','.m4a') else []
            stem_container=len(streams)==5 and (bool(ni_labels) or path.name.lower().endswith(('.stem.mp4','.stem.m4a')))
            if ni_labels:
                titles=['Full mix']+[label or f'Stem {i+1}' for i,label in enumerate(ni_labels)]
            named_stems=all(any(w in t.lower() for w in STEMS) for t in titles)
            for n,s in enumerate(streams):
                ctx=s.codec_context
                names=[c.name for c in ctx.layout.channels]
                if not names:
                    raise ValueError(f'Unknown channel layout in {path.name}')
                idx=len(sources)
                sources.append(Source(path,s.index,ctx.layout.name,origin,len(names)))
                if s.duration is not None and s.time_base:
                    end=max(end,float(((s.start_time or 0)+s.duration)*s.time_base)-origin)
                enabled=(n!=0) if stem_container else (n==0 or named_stems)
                title=titles[n] if titles[n] not in ('','SoundHandler','Core Media Audio') else ''
                if not title:
                    title=path.stem if len(streams)==1 else f'Track {n+1}'
                    if stem_container:
                        title='Full mix' if n==0 else f'Stem {n}'
                if len(paths)>1 and len(streams)>1:
                    title=f'{path.stem} · {title}'
                lang=s.metadata.get('language','')
                fmt=f'{ctx.name.upper()} · {ctx.sample_rate/1000:g} kHz'
                if lang and lang!='und':
                    fmt+=f' · {lang}'
                matrix=channel_mix(names)
                if len(names)<=2:
                    tracks.append(Track(title,fmt+(' · Mono' if len(names)==1 else ' · Stereo'),idx,matrix,enabled))
                else:
                    for ch,name in enumerate(names):
                        one=np.zeros_like(matrix)
                        one[ch]=matrix[ch]
                        label=LABELS.get(name,name if name!='NONE' else f'Channel {ch+1}')
                        tracks.append(Track(label,(title+' · ' if len(streams)>1 or len(paths)>1 else '')+fmt+' · '+name,idx,one,enabled))
    return Project(sources,tracks,end,Path(paths[0]).name if len(paths)==1 else f'{len(paths)} aligned stem files')

class Reader:
    def __init__(self,source,offset,stack):
        import av
        media=stack.enter_context(av.open(str(source.path)))
        stream=media.streams[source.index]
        if offset:
            try:
                media.seek(int((source.origin+offset/RATE)*av.time_base),backward=True)
            except av.FFmpegError:
                # Some audio formats require decoding forward from the start.
                media=stack.enter_context(av.open(str(source.path)))
                stream=media.streams[source.index]
        self.frames=self.decode(media,stream,source)
        self.pending=None
        self.done=False
        self.channels=source.channels

    @staticmethod
    def decode(media,stream,source):
        import av
        resampler=av.AudioResampler(format='fltp',layout=source.layout,rate=RATE)
        cursor=0
        def convert(frames):
            nonlocal cursor
            for out in frames:
                if out.pts is not None and out.time_base:
                    cursor=round((float(out.pts*out.time_base)-source.origin)*RATE)
                buf=np.ascontiguousarray(out.to_ndarray().T)
                start=cursor
                cursor+=len(buf)
                yield start,buf
        for frame in media.decode(stream):
            yield from convert(resampler.resample(frame))
        yield from convert(resampler.resample(None))

    def read(self,start,count):
        result=np.zeros((count,self.channels),np.float32)
        extent=0
        while not self.done:
            if self.pending is None:
                self.pending=next(self.frames,None)
                if self.pending is None:
                    self.done=True
                    break
            at,buf=self.pending
            end=at+len(buf)
            if at>=start+count:
                return result,count
            lo,hi=max(start,at),min(start+count,end)
            if hi>lo:
                result[lo-start:hi-start]=buf[lo-at:hi-at]
                extent=max(extent,hi-start)
            if end>start+count:
                break
            self.pending=None
        return result,extent

def output_device():
    speaker=AudioUtilities.GetSpeakers()
    name=speaker.FriendlyName
    wasapi=next(i for i,a in enumerate(sd.query_hostapis()) if a['name']=='Windows WASAPI')
    ids=[i for i,d in enumerate(sd.query_devices()) if d['hostapi']==wasapi and d['name']==name and d['max_output_channels']>=2]
    if len(ids)!=1:
        raise RuntimeError(f'Could not open audio output: {name}')
    return ids[0],speaker.id

class Player:
    def __init__(self):
        self.cv=Condition()
        self.project=None
        self.settings=[]
        self.pos=self.version=0
        self.playing=self.closed=False
        self.error=''
        self.thread=Thread(target=self.run,daemon=True,name='Stem mixer')
        self.thread.start()

    def load(self,project):
        with self.cv:
            self.project=project
            self.settings=[(1.,not t.enabled,False) for t in project.tracks]
            self.reset(0,False)

    def reset(self,frame,playing):
        with self.cv:
            self.version+=1
            self.pos=max(0,int(frame))
            self.playing=playing
            self.error=''
            self.cv.notify_all()

    def close(self):
        with self.cv:
            self.closed=True
            self.reset(0,False)
        self.thread.join(2)

    def run(self):
        comtypes.CoInitialize()
        try:
            while True:
                with self.cv:
                    self.cv.wait_for(lambda:self.closed or self.playing)
                    if self.closed:
                        return
                    version,project,start=self.version,self.project,self.pos
                try:
                    self.play_project(project,version,start)
                except Exception as exc:
                    with self.cv:
                        if self.version==version:
                            self.playing=False
                            self.error=str(exc)
        finally:
            comtypes.CoUninitialize()

    def play_project(self,project,version,pos):
        idx,endpoint=output_device()
        tone = None if endpoint.lower() == MIX_ENDPOINT.lower() else LiveEQ()
        with ExitStack() as stack:
            readers=[Reader(s,pos,stack) for s in project.sources]
            stream=stack.enter_context(sd.OutputStream(samplerate=RATE,device=idx,channels=2,dtype='float32',latency='low'))
            next_check=time.monotonic()+1
            while True:
                with self.cv:
                    if self.version!=version:
                        stream.abort()
                        return
                    settings=self.settings.copy()
                if time.monotonic()>=next_check:
                    if AudioUtilities.GetSpeakers().id!=endpoint:
                        stream.abort()
                        return # reopen the current default at the saved position
                    next_check=time.monotonic()+1
                matrices=[np.zeros((s.channels,2),np.float32) for s in project.sources]
                any_solo=any(solo for _,_,solo in settings)
                for t,(gain,mute,solo) in zip(project.tracks,settings):
                    if not mute and (not any_solo or solo):
                        matrices[t.stream]+=t.matrix*gain
                mix=np.zeros((BLOCK,2),np.float32)
                used=0
                for reader,matrix in zip(readers,matrices):
                    samples,n=reader.read(pos,BLOCK)
                    used=max(used,n)
                    mix+=samples @ matrix
                if not used:
                    with self.cv:
                        if self.version==version:
                            self.playing=False
                            self.pos=0
                    return
                samples = mix[:used]
                if tone is not None:
                    samples = tone.process(samples)
                stream.write(np.clip(samples,-1,1))
                pos+=used
                with self.cv:
                    if self.version==version:
                        self.pos=pos
