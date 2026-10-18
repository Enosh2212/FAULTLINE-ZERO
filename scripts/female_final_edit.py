"""Reference-inspired motion edit, real captures, neural narration and timed captions."""
from pathlib import Path
import sys,json,asyncio,subprocess,math,io,wave,bisect,textwrap
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'output/demo'; EDIT=OUT/'female-final';EDIT.mkdir(exist_ok=True)
sys.path.insert(0,str(OUT/'voice-tools'));import edge_tts
FF=Path(r'C:\Users\Enosh\AppData\Roaming\Python\Python314\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe')
FP=Path(r'C:\Users\Enosh\Downloads\krita-x64-5.3.3\krita-x64-5.3.3\bin\ffprobe.exe')
FPS=30;W=1920;H=1080;SR=48000
WHITE='#f2f6f3';MINT='#b5e6c6';MUTED='#9bb0a5';DARK='#080e0b'
manifest={x['name']:x for x in json.loads((OUT/'capture-manifest.json').read_text())}
for name in ['graph-impact','graph-neighbors']:
 if 'hq-'+name in manifest:manifest[name]=manifest['hq-'+name]
SCENES=[
 ('hook',2,'Your tests passed.','',None,'Your tests passed.'),
 ('question',3,'But what could your','code change break?',None,'But what could your code change break?'),
 ('brand',3,'FAULTLINE ZERO','Understand the impact. Before the merge.',None,'Meet Faultline Zero.'),
 ('landing-final',6,'Understand the impact.','Before the merge.',(170,80,1750,900),'Graph-native intelligence that follows the impact before the merge.'),
 ('overview',5,'Every change has context.','A server-verified workspace.',(250,65,1890,435),'Your repository. Your workspace. Every investigation, grounded in evidence.'),
 ('repository',6,'Source. Connected.','Enosh2212 / risklens-ai · snapshot 8af3a444',(320,185,1790,750),'This is RiskLens AI. A real GitHub repository, indexed at a specific commit.'),
 ('coverage',5,'Code becomes context.','GitHub → Python AST → Dependency Graph',(300,190,1850,765),'Authorized Python source becomes an A S T and a dependency graph.'),
 ('snapshot',5,'Stored in FalkorDB.','Read-only facts. Explicit coverage limits.',(950,240,1830,720),'Falkor D B stores the graph. Runtime behavior stays unverified.'),
 ('graph-impact',8,'Follow the dependency.','main → process_features · CALLS',(430,460,1530,930),'Select a function... and follow the impact. Here, main calls process features. Real relationships, with a clear direction.'),
 ('graph-neighbors',8,'Explore the neighborhood.','Incoming callers. Source provenance. Actual relationships.',(430,460,1530,930),'Now, expand the neighborhood. Inspect incoming callers and source provenance. Every connection comes from the indexed graph.'),
 ('graph-structure',5,'See the architecture.','Files. Modules. Hierarchy.',(690,515,1190,965),'Switch to repository structure to explore files, modules, and their hierarchy.'),
 ('cypher',9,'The graph answers.','Actual read-only query · indexed RiskLens snapshot',None,'Here is the actual read-only Cypher query, executed against Falkor D B. Its results connect real callers to callees in the indexed snapshot.'),
 ('investigation',9,'One real pull request.','An evidence-backed verdict.',(320,185,1790,750),'Now, a real pull request. The source was parsed, but no applicable verified business invariants were found. The verdict? Inconclusive.'),
 ('evidence',8,'Documentation only.','Changed symbol: build_features · DOCS_ONLY',(320,210,1790,780),'Build features changed documentation only. Its executable A S T is unchanged. Runtime behavior remains unverified.'),
 ('github-check',8,'An honest check. Published.','Neutral / INCONCLUSIVE · github.com/Enosh2212/risklens-ai',(610,210,1850,1020),'The agent publishes a neutral GitHub check, showing the classification, coverage gaps, and evidence behind its honest conclusion.'),
 ('workflow',6,'From source to a scoped check.','Illustrative product workflow · not live telemetry',(400,65,1500,690),'Connect GitHub, index source, trace impact, and publish an evidence-backed check.'),
 ('outro',9,'FAULTLINE ZERO','Graph-Native Pre-Merge Intelligence',None,'Faultline Zero. Understand the impact before the merge. Built with Falkor D B.')]
TOTAL=sum(s[1] for s in SCENES)
def ff(args,**kw):return subprocess.run([str(FF),'-hide_banner','-loglevel','error','-y',*map(str,args)],check=True,**kw)
def duration(p):return float(subprocess.check_output([str(FP),'-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True))
async def voices():
 sem=asyncio.Semaphore(3)
 async def one(i,s):
  audio=EDIT/f'voice-{i:02}.mp3';meta=EDIT/f'voice-{i:02}.json'
  if audio.exists() and meta.exists():return
  async with sem:
   words=[]
   for attempt in range(2):
    try:
     with audio.open('wb') as f:
      async for chunk in edge_tts.Communicate(s[5],'en-US-AvaMultilingualNeural',rate=('-5%' if i in [0,1,2,16] else '+1%'),pitch=('+3Hz' if i in [1,3,8,9] else '-2Hz' if i in [12,13,14] else '+0Hz'),boundary='WordBoundary').stream():
       if chunk['type']=='audio':f.write(chunk['data'])
       elif chunk['type']=='WordBoundary':words.append({'text':chunk['text'],'start':chunk['offset']/1e7,'duration':chunk['duration']/1e7})
     meta.write_text(json.dumps(words));print('Narration ready',s[0],flush=True);return
    except Exception:
     if attempt:raise
     words=[]
 await asyncio.gather(*(one(i,s) for i,s in enumerate(SCENES)))
asyncio.run(voices())

# Original ambient score, synthesized here; no reference audio is reused.
samples=int(TOTAL*SR);music=np.zeros(samples,dtype=np.float32);voice=np.zeros(samples,dtype=np.float32)
chords=[[110,164.8138,220,261.6256],[87.3071,130.8128,174.6141,220],[130.8128,195.9977,261.6256,329.6276],[97.9989,146.8324,195.9977,261.6256]]
for k,start in enumerate(np.arange(0,TOTAL,6.0)):
 n=min(int(7.5*SR),samples-int(start*SR));t=np.arange(n)/SR;env=(1-np.exp(-t/1.0))*np.minimum(1,(7.5-t)/1.7)
 pad=sum(np.sin(2*np.pi*f*t+.08*np.sin(.5*t+j))*.25 for j,f in enumerate(chords[k%4]))
 music[int(start*SR):int(start*SR)+n]+=(pad*env*.012).astype(np.float32)
for beat in np.arange(0,TOTAL,.625):
 n=min(int(.24*SR),samples-int(beat*SR));t=np.arange(n)/SR
 pulse=np.sin(2*np.pi*55*t)*np.exp(-t*25)*.018
 music[int(beat*SR):int(beat*SR)+n]+=pulse.astype(np.float32)
timeline=[];offset=0;caption_events=[];chapters=[0,8,35,65,90]
for i,s in enumerate(SCENES):
 p=EDIT/f'voice-{i:02}.mp3';words=json.loads((EDIT/f'voice-{i:02}.json').read_text());dur=words[-1]['start']+words[-1]['duration']+.12;available=s[1]-.36;speed=max(1,dur/available)
 # Time-compress only where needed to fit the scene, preserving pitch.
 data=subprocess.check_output([str(FF),'-v','error','-i',str(p),'-af',f'atrim=end={dur:.6f},atempo={speed:.6f},afade=t=in:d=0.015','-f','f32le','-ac','1','-ar',str(SR),'-'])
 arr=np.frombuffer(data,dtype='<f4').copy();peak=max(.01,float(np.max(np.abs(arr))));arr*=.66/peak
 st=int((offset+.16)*SR);n=min(len(arr),samples-st);voice[st:st+n]+=arr[:n]
 words=json.loads((EDIT/f'voice-{i:02}.json').read_text());groups=[]
 for a in range(0,len(words),7):
  g=words[a:a+7];begin=.16+g[0]['start']/speed;end=.16+(g[-1]['start']+g[-1]['duration'])/speed
  group={'start':begin,'end':min(s[1]-.08,end+.12),'text':' '.join(x['text'] for x in g)};groups.append(group)
  caption_events.append((offset+group['start'],offset+group['end'],group['text']))
 timeline.append({'start':offset,'duration':s[1],'name':s[0],'caption_groups':groups,'speed':speed});offset+=s[1]
print('Narration synchronized; maximum tempo',max(x['speed'] for x in timeline),flush=True)
env=np.minimum(1,np.arange(samples)/(SR*.7))*np.minimum(1,(samples-np.arange(samples))/(SR*2))
mix=(voice+music)*env;mix=np.clip(mix,-.94,.94);stereo=np.stack([mix,mix],axis=1)
with wave.open(str(EDIT/'original-score-and-narration.wav'),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((stereo*32767).astype('<i2').tobytes())

FONTS={}
def font(size,bold=False,mono=False):
 key=(size,bold,mono)
 if key not in FONTS:FONTS[key]=ImageFont.truetype('C:/Windows/Fonts/'+('consola.ttf' if mono else 'segoeuib.ttf' if bold else 'segoeui.ttf'),size)
 return FONTS[key]
def text(im,xy,words,size=30,color=WHITE,bold=False,alpha=1,mono=False,anchor=None):
 if alpha<=0:return
 f=font(size,bold,mono);bbox=ImageDraw.Draw(im).textbbox(xy,words,font=f,anchor=anchor);x0,y0,x1,y1=map(int,bbox)
 if x1<=x0 or y1<=y0:return
 layer=Image.new('RGBA',(x1-x0+3,y1-y0+3));d=ImageDraw.Draw(layer);rgb=tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4));d.text((xy[0]-x0,xy[1]-y0),words,font=f,fill=rgb+(int(min(1,alpha)*255),),anchor=anchor);im.alpha_composite(layer,(x0,y0))
def ease(x):x=max(0,min(1,x));return 1-(1-x)**3
def center(im,y,words,size=72,color=WHITE,alpha=1,bold=False):text(im,(W//2,y),words,size,color,bold,alpha,anchor='mt')
# Small gradients expanded smoothly: lighting, not a flat background.
yy,xx=np.mgrid[0:270,0:480];r=np.exp(-(((xx-240)/170)**2+((yy-205)/85)**2));bg=np.zeros((270,480,3),dtype=np.uint8)
for c,(a,b) in enumerate([(5,11),(10,30),(8,18)]):bg[:,:,c]=a+(r*b).astype(np.uint8)
BASE=Image.fromarray(bg).resize((W,H),Image.Resampling.BICUBIC).convert('RGBA')
d=ImageDraw.Draw(BASE)
for x in range(36,W,72):
 for y in range(30,H,72):d.ellipse((x,y,x+1,y+1),fill=(90,132,107,32))
MASK=Image.new('L',(1760,700),0);ImageDraw.Draw(MASK).rounded_rectangle((0,0,1759,699),radius=26,fill=255)
shade=Image.new('RGBA',(W,H));ImageDraw.Draw(shade).rounded_rectangle((70,186,1850,914),30,fill=(0,0,0,180));shade=shade.filter(ImageFilter.GaussianBlur(20))
def shell(t,chapter):
 im=BASE.copy();d=ImageDraw.Draw(im)
 d.rounded_rectangle((72,40,110,78),10,fill=MINT);d.line((95,46,84,60,96,60,87,72),fill='#10331f',width=3)
 text(im,(126,43),'FAULTLINE ZERO',23,WHITE,True);text(im,(1837,49),'HACKATHON FILM  /  BUILT WITH FALKORDB',17,MUTED,anchor='rt')
 names=[];width=337
 for i,name in enumerate(names):
  x=75+i*356;active=i==chapter;d=ImageDraw.Draw(im);d.rounded_rectangle((x,1003,x+width,1045),11,fill=('#b5e6c6' if active else '#15251c'))
  text(im,(x+width//2,1012),name,17,'#102a1b' if active else MUTED,True,anchor='mt')
 pass
 return im
def captions(im,t,groups):
 g=next((g for g in groups if g['start']<=t<=g['end']),None)
 if not g:return
 lines=textwrap.wrap(g['text'],width=76);a=min(1,(t-g['start'])*10,(g['end']-t)*10);y=922 if len(lines)==1 else 906
 for j,line in enumerate(lines):center(im,y+j*37,line,30,WHITE,max(.0,a),True)
def kinetic_line(im,y,words,t,start=0,size=80,color=WHITE):
 f=font(size,True);d=ImageDraw.Draw(im);parts=words.split(' ');widths=[d.textlength(w+' ',font=f) for w in parts];x=(W-sum(widths))/2
 for i,(word,wi) in enumerate(zip(parts,widths)):
  a=ease((t-start-i*.11)/.48);text(im,(x,y+(1-a)*28),word,size,color,True,a);x+=wi
def logo_orbit(im,t):
 d=ImageDraw.Draw(im);cx=960;cy=327
 d.ellipse((cx-56,cy-56,cx+56,cy+56),fill='#142d1e',outline='#9bcaaa',width=2)
 d.line((cx+14,cy-33,cx-18,cy+4,cx+10,cy+4,cx-12,cy+36),fill=MINT,width=7)
 for i in range(3):
  angle=t*.7+i*2.094;x=cx+math.cos(angle)*103;y=cy+math.sin(angle)*38;d.ellipse((x-4,y-4,x+4,y+4),fill=MINT)
query=json.loads((OUT/'cypher-evidence.json').read_text(encoding='utf-8-sig'))
def graphics(s,t,absolute,groups):
 name,sec,title,sub,_,_=s;chapter=0 if name!='outro' and name!='cypher' else 2 if name=='cypher' else 4;im=shell(absolute,chapter)
 if name=='hook':
  text(im,(960,328),'THE PROBLEM',21,MINT,True,anchor='mt');kinetic_line(im,430,title,t,.12,91)
  center(im,580,'A passing suite is only the beginning.',29,MUTED,ease((t-.7)/.7))
 elif name=='question':
  kinetic_line(im,350,title,t,.08,77);kinetic_line(im,455,sub,t,.55,89,MINT)
  center(im,618,'Follow what the diff cannot show.',29,MUTED,ease((t-1.4)/.7))
 elif name=='brand':
  logo_orbit(im,t);kinetic_line(im,445,title,t,.12,92);center(im,584,sub,33,MINT,ease((t-.75)/.7))
 elif name=='cypher':
  text(im,(80,110),title,54,WHITE,True);text(im,(83,173),sub,24,MINT)
  d=ImageDraw.Draw(im);d.rounded_rectangle((80,232,1840,883),25,fill='#102018',outline='#365742',width=2)
  for j,c in enumerate(['#d38078','#d4b67b','#95caa6']):d.ellipse((110+j*23,254,121+j*23,265),fill=c)
  text(im,(1820,250),'CYPHER  /  READ ONLY',17,MUTED,anchor='rt')
  for j,line in enumerate(query['query'].splitlines()):text(im,(115,292+j*41),line,26,WHITE,False,ease((t-.2-j*.2)/.45),True)
  text(im,(115,581),'CALLER',18,MUTED,True,ease((t-2)/.5));text(im,(875,581),'CALLEE',18,MUTED,True,ease((t-2)/.5))
  for j,row in enumerate(query['rows']):
   a=ease((t-2.4-j*.25)/.5);text(im,(115,624+j*37),row[0],26,MINT,False,a,True);text(im,(790,624+j*37),'→',27,MUTED,False,a);text(im,(875,624+j*37),row[1],26,WHITE,False,a,True)
 elif name=='outro':
  if t<3.2:
   center(im,248,'From a pull request to a scoped check.',49,WHITE,ease(t/.5),True)
   steps=['GitHub PR','Python AST','FalkorDB','Impact','GitHub Check']
   for j,label in enumerate(steps):
    a=ease((t-.25-j*.27)/.5);x=100+j*350;d=ImageDraw.Draw(im);y=431+int((1-a)*30)
    d.rounded_rectangle((x,y,x+315,y+106),20,fill='#193626',outline='#5f9672',width=2);text(im,(x+157,y+34),label,29,MINT,True,a,anchor='mt')
    if j<4:text(im,(x+325,y+31),'→',29,MINT,False,a)
   center(im,648,'Understand the impact. Before the merge.',31,MUTED,ease((t-1.5)/.8))
  else:
   logo_orbit(im,t);kinetic_line(im,435,title,t-3.2,.03,91);center(im,567,sub,35,MINT,ease((t-3.6)/.7));center(im,657,'Understand the impact. Before the merge.',30,WHITE,ease((t-4)/.7));center(im,773,'Built with FalkorDB',25,MUTED,ease((t-4.4)/.7))
 captions(im,t,groups);return im
def source_scene(s):
 frames=manifest[s[0]]['frames'];return frames,[f['t'] for f in frames]
def software(s,t,absolute,groups,cache):
 name,sec,title,sub,roi,_=s;chapter=1 if absolute<35 else 2 if absolute<65 else 3 if absolute<90 else 4
 im=shell(absolute,chapter);entry=ease(t/.7);text(im,(80,100+(1-entry)*17),title,45,WHITE,True,entry);text(im,(83,158),sub,23,MINT,False,ease((t-.12)/.6))
 frames,times=cache['frames'],cache['times'];capture_t=min(t,manifest[name]['seconds']-.05);idx=max(0,min(len(frames)-1,bisect.bisect_right(times,capture_t)-1))
 if cache.get('idx')!=idx:
  cache['image']=Image.open(OUT/frames[idx]['file']).convert('RGB');cache['idx']=idx
 image=cache['image'].crop(roi).filter(ImageFilter.UnsharpMask(radius=1.1,percent=115,threshold=3))
 # Slow camera push and smooth slide-in are edit transforms of genuine pixels.
 window=(1760,700);scale=min(window[0]/image.width,window[1]/image.height)*(1+.075*ease(t/sec))
 nw,nh=int(image.width*scale),int(image.height*scale);image=image.resize((nw,nh),Image.Resampling.LANCZOS)
 canvas=Image.new('RGB',window,DARK);canvas.paste(image,((1760-nw)//2,(700-nh)//2));canvas=canvas.convert('RGBA');canvas.putalpha(MASK)
 y=205+int((1-entry)*25);im.alpha_composite(shade);im.alpha_composite(canvas,(80,y))
 d=ImageDraw.Draw(im);d.rounded_rectangle((80,y,1839,y+699),26,outline='#375640',width=1)
 text(im,(1810,y+15),'ACTUAL SOFTWARE CAPTURE',14,MUTED,anchor='rt')
 if name in ['graph-impact','graph-neighbors']:
  # An editorial callout, not a fabricated graph node or relationship.
  d.rounded_rectangle((105,810,735,866),14,fill='#14291d',outline='#507b5e',width=1)
  text(im,(127,823),'CALLS  /  main → process_features',25,MINT,True,ease((t-.7)/.5))
 if name=='graph-structure':text(im,(120,823),'Recorded hierarchy · repository / module / file',24,MINT,True)
 captions(im,t,groups);return im

silent=EDIT/'picture.mp4';log=(EDIT/'render.log').open('w')
cmd=[str(FF),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','1920x1080','-framerate','30','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','15','-pix_fmt','yuv420p','-threads','4',str(silent)]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
try:
 for i,(s,info) in enumerate(zip(SCENES,timeline)):
  cache={}
  if s[4]:cache['frames'],cache['times']=source_scene(s)
  first=None
  for n in range(s[1]*FPS):
   t=n/FPS;absolute=info['start']+t
   im=software(s,t,absolute,info['caption_groups'],cache) if s[4] else graphics(s,t,absolute,info['caption_groups'])
   # Short cinematic dissolves; no hard black flashes between scenes.
   if n<14 and i>0 and previous is not None:
    a=ease(n/14)
    if i in [3,5,8,11,14]:
     mode=i%3
     if mode==0:
      transition=BASE.copy();transition.alpha_composite(previous,(-int(a*220),0));transition.alpha_composite(im,(int((1-a)*W),0));im=transition
     elif mode==1:
      z=1.09-.09*a;big=im.resize((int(W*z),int(H*z)),Image.Resampling.LANCZOS);big=big.crop(((big.width-W)//2,(big.height-H)//2,(big.width+W)//2,(big.height+H)//2));im=Image.blend(previous.filter(ImageFilter.GaussianBlur(5*a)),big,a)
     else:
      mask=Image.new('L',(W,H),0);ImageDraw.Draw(mask).rectangle((0,0,int(W*a),H),fill=255);im=Image.composite(im,previous,mask)
    else:im=Image.blend(previous,im,a)
   if absolute>TOTAL-.7:im=Image.blend(Image.new('RGBA',im.size,'black'),im,max(0,(TOTAL-absolute)/.7))
   p.stdin.write(im.convert('RGB').tobytes())
   if n==s[1]*FPS//2:im.convert('RGB').save(EDIT/f'proof-{i:02}.jpg',quality=92)
  previous=im
  print('Picture rendered',s[0],flush=True)
finally:p.stdin.close()
if p.wait():raise RuntimeError((EDIT/'render.log').read_text())
log.close()
final=OUT/'FAULTLINE_ZERO_Final_Female_Voice.mp4'
ff(['-i',silent,'-i',EDIT/'original-score-and-narration.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-c:a','aac','-b:a','256k','-ar','48000','-t',TOTAL,'-movflags','+faststart',final])
def stamp(t):
 ms=int(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
srt='\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{line}' for i,(a,b,line) in enumerate(caption_events))
(OUT/'FAULTLINE_ZERO_Final_Captions.srt').write_text(srt,encoding='utf-8')
report=['FAULTLINE ZERO — PREMIUM NARRATED EDIT','105 seconds, 1920×1080, 30 fps, H.264 + AAC stereo.','79 seconds (75.2%) genuine captured software. Animated camera framing and captions are editorial overlays.','Original synthesized ambient score. Synthetic female neural voice, en-US-AvaMultilingualNeural, with scene-specific pacing and pitch. No reference music, logos, or footage reused.','RiskLens investigation remains INCONCLUSIVE. No fresh execution or indexing progress was fabricated.','REFERENCE INFLUENCE: kinetic centered typography, short narrative beats, smooth camera pushes, product close-ups.','','TIMED VOICEOVER']
for s,info in zip(SCENES,timeline):report.append(f'{info["start"]:03d}–{info["start"]+s[1]:03d}s | {s[5]}')
(OUT/'FAULTLINE_ZERO_Final_Voiceover_Script.txt').write_text('\n'.join(report),encoding='utf-8')
probe=json.loads(subprocess.check_output([str(FP),'-v','error','-show_streams','-show_format','-of','json',str(final)],text=True));(OUT/'premium-verification.json').write_text(json.dumps(probe,indent=2))
assert len(probe['streams'])==2;assert next(x for x in probe['streams'] if x['codec_type']=='video')['width']==1920
assert 104.9<=float(probe['format']['duration'])<=105.1
ff(['-v','error','-i',final,'-f','null','-'])
print('FINAL VERIFIED',str(final),final.stat().st_size,flush=True)
