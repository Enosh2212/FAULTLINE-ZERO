"""Edit genuine IAB capture frames into the final captioned hackathon film."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json, subprocess, textwrap, math

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/demo'
FF=Path(r'C:\Users\Enosh\AppData\Roaming\Python\Python314\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe')
PROBE=Path(r'C:\Users\Enosh\Downloads\krita-x64-5.3.3\krita-x64-5.3.3\bin\ffprobe.exe')
W,H=1920,1080
BG='#080d0b'; WHITE='#eff5f0'; GREEN='#a5d7b5'; MUTED='#99aaa1'
def font(n,bold=False,mono=False):
    return ImageFont.truetype(str(Path('C:/Windows/Fonts')/('consola.ttf' if mono else 'segoeuib.ttf' if bold else 'segoeui.ttf')),n)
def txt(d,xy,s,n=30,fill=WHITE,bold=False,mono=False):d.text(xy,s,font=font(n,bold,mono),fill=fill)
def base(kicker):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    for x in range(0,W,64):
        for y in range(0,H,64):d.ellipse((x,y,x+1,y+1),fill='#1b2b22')
    d.rounded_rectangle((68,54,114,100),12,fill='#a5d7b5');txt(d,(79,55),'ϟ',32,'#112319',True)
    txt(d,(132,59),'FAULTLINE ZERO',27,bold=True)
    txt(d,(1150,66),kicker,20,MUTED)
    return im
def save(im,name):p=OUT/(name+'.png');im.save(p);return p
def card(name,kicker,title,subtitle):
    im=base(kicker);d=ImageDraw.Draw(im)
    for i,line in enumerate(title.split('\n')):txt(d,(112,340+i*105),line,78,WHITE,True)
    txt(d,(116,625),subtitle,30,GREEN)
    d.line((116,720,1804,720),fill='#263c30',width=2)
    return save(im,name)
def run(args):
    p=subprocess.run([str(FF),'-hide_banner','-loglevel','error','-y',*map(str,args)],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr[-6000:])
def encode(args,path,seconds):
    run([*args,'-t',seconds,'-an','-r','30','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',path])
segments=[]
def still(name,path,seconds):
    dest=OUT/(name+'.mp4')
    encode(['-loop','1','-i',path,'-vf',f'scale=1920:1080,setsar=1,fade=t=in:st=0:d=0.35,fade=t=out:st={seconds-.35}:d=0.35'],dest,seconds)
    segments.append(dest);print('Rendered',name,flush=True)

manifest={s['name']:s for s in json.loads((OUT/'capture-manifest.json').read_text())}
script=[]
def footage(name,seconds,title,sub,crop=None):
    s=manifest[name];lst=OUT/(name+'.ffconcat')
    lines=['ffconcat version 1.0']
    for i,f in enumerate(s['frames']):
        duration=(s['frames'][i+1]['t'] if i+1<len(s['frames']) else seconds)-f['t']
        lines += ["file '"+(OUT/f['file']).as_posix()+"'",'duration '+str(max(.001,duration))]
    lines += ["file '"+(OUT/s['frames'][-1]['file']).as_posix()+"'"]
    lst.write_text('\n'.join(lines))
    overlay=base('ACTUAL SOFTWARE CAPTURE  /  RISKLENS AI').convert('RGBA')
    d=ImageDraw.Draw(overlay)
    # The transparent window is filled only by actual captured pixels.
    d.rectangle((60,134,1860,900),fill=(0,0,0,0))
    txt(d,(72,930),title,36,WHITE,True);txt(d,(74,989),sub,25,GREEN)
    ov=save(overlay,name+'-overlay');dest=OUT/(name+'.mp4')
    # Crop reframes the camera only; it does not alter records or graph facts.
    pre=(f'crop={crop},' if crop else '')
    filt=f'[0:v]{pre}scale=1800:766:force_original_aspect_ratio=decrease,pad=1800:766:(ow-iw)/2:(oh-ih)/2:color=0x080d0b,setsar=1,fps=30[v];[1:v][v]overlay=60:134:shortest=1,fade=t=in:st=0:d=0.2[out]'
    encode(['-f','concat','-safe','0','-i',lst,'-loop','1','-i',ov,'-filter_complex_threads','1','-filter_complex',filt,'-map','[out]'],dest,seconds)
    segments.append(dest);script.append((seconds,title,sub));print('Rendered',name,flush=True)

still('01-opening',card('opening','PRE-MERGE INTELLIGENCE','Your tests passed.','A passing suite is only the beginning.'),2)
still('02-question',card('question','FOLLOW THE IMPACT','But what could your\ncode change break?','Code changes travel farther than the diff.'),3)
still('03-intro-brand',card('intro-brand','GRAPH-NATIVE INVESTIGATION','FAULTLINE ZERO','Understand the impact. Before the merge.'),3)
footage('landing-final',6,'Understand the impact. Before the merge.','Real application · authenticated session · no mock records')
# Only the overview summary is framed: unrelated private repository names are excluded.
footage('overview',5,'One connected workspace. Evidence in context.','Live workspace summary · outcomes retain their original meaning','1640:370:250:65')
footage('repository',6,'An authorized GitHub repository. A concrete snapshot.','Enosh2212/risklens-ai · indexed commit 8af3a444','1640:760:250:80')
footage('coverage',10,'GitHub source → Python AST → dependency graph → FalkorDB','Pipeline explanation over a completed index record — not live indexing progress','1550:575:300:190')
footage('snapshot',10,'Static facts with explicit coverage limits.','Read-only analysis. Dynamic calls and runtime behavior may remain unresolved.','1550:575:300:190')
footage('graph-impact',8,'Dependency traversal: main → process_features','Actual CALLS edge · src/etl/load_real_dataset.py · not runtime execution proof','1520:625:300:345')
footage('graph-neighbors',8,'Follow recorded callers. Expand the neighborhood.','Selected function and incoming relationships are returned from the indexed graph.','1520:625:300:345')
footage('graph-structure',5,'Files and modules give every symbol a place.','Repository Structure view · recorded hierarchy · no invented edges','1520:625:300:345')

e=json.loads((OUT/'cypher-evidence.json').read_text(encoding='utf-8-sig'))
im=base('ACTUAL READ-ONLY FALKORDB QUERY');d=ImageDraw.Draw(im)
txt(d,(90,150),'The graph is queried. Not just drawn.',52,WHITE,True)
txt(d,(94,225),'Enosh2212/risklens-ai  /  snapshot '+e['revision'][:12],24,GREEN)
d.rounded_rectangle((84,290,1836,940),22,fill='#101b15',outline='#2a4334',width=2)
for i,line in enumerate(e['query'].splitlines()):txt(d,(118,325+i*44),line,27,WHITE,mono=True)
txt(d,(118,620),'CALLER',21,MUTED,True);txt(d,(815,620),'CALLEE',21,MUTED,True)
for i,row in enumerate(e['rows']):
    txt(d,(118,665+i*40),str(row[0]),27,GREEN,mono=True)
    txt(d,(735,665+i*40),'→',27,MUTED)
    txt(d,(815,665+i*40),str(row[1]),27,WHITE,mono=True)
txt(d,(92,987),'Real query results · tenant-isolated graph · repository + revision scoped',24,MUTED)
still('query-evidence',save(im,'cypher-card'),9)

footage('investigation',9,'A real pull request. An evidence-backed verdict.','RiskLens PR #1 · INCONCLUSIVE · no applicable verified business invariants','1640:760:250:80')
footage('evidence',8,'Changed symbol: build_features. Classification: DOCS_ONLY.','Executable AST unchanged · callers/tests not recorded for this change · runtime unverified','1640:760:250:80')
footage('github-check',8,'Published to GitHub as a neutral check.','No false regression claim. No false assurance. The coverage limits stay visible.','1610:940:280:120')
footage('workflow',6,'Connect → Index → Detect PR → Trace → Verify → Publish','Illustrative product workflow — not live system telemetry','1550:600:280:60')

im=base('BUILT WITH FALKORDB');d=ImageDraw.Draw(im)
txt(d,(112,250),'FAULTLINE ZERO',93,WHITE,True)
txt(d,(116,380),'Graph-Native Pre-Merge Intelligence',45,GREEN)
txt(d,(117,480),'Understand the impact. Before the merge.',33,WHITE)
steps=['GitHub PR','Python AST','FalkorDB','Impact analysis','GitHub Check']
for i,s in enumerate(steps):
    x=116+i*345;d.rounded_rectangle((x,645,x+298,735),17,fill='#14251b',outline='#3d624a',width=2);txt(d,(x+20,670),s,27,WHITE,True)
    if i<4:txt(d,(x+309,670),'→',28,GREEN)
txt(d,(116,840),'Built with FalkorDB',31,GREEN,True)
txt(d,(116,922),'Actual RiskLens AI snapshot + PR Check · runtime coverage reported honestly',23,MUTED)
still('outro',save(im,'outro-card'),9)
concat=OUT/'final.ffconcat';concat.write_text('ffconcat version 1.0\n'+'\n'.join("file '"+p.as_posix()+"'" for p in segments))
final=OUT/'FAULTLINE_ZERO_Hackathon_Demo.mp4'
run(['-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',final])
probe=json.loads(subprocess.check_output([str(PROBE),'-v','error','-show_format','-show_streams','-of','json',str(final)],text=True))
(OUT/'final-verification.json').write_text(json.dumps(probe,indent=2))
v=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (v['width'],v['height'],v['codec_name'])==(1920,1080,'h264')
assert 114<=float(probe['format']['duration'])<=116
report=['FAULTLINE ZERO — FINAL HACKATHON DEMO','Duration: 115 seconds. 1920×1080 H.264 MP4. Silent, captioned viewing.','89 seconds (77.4%) genuine authenticated/application/GitHub footage. Capture frames retain their recorded timestamps; output is 30 fps.','26 seconds original opening, actual-query evidence card, and closing graphics.','No new indexing job or runtime test execution was recorded. Existing snapshot and completed investigation were demonstrated.','Actual Check: https://github.com/Enosh2212/risklens-ai/runs/117658118768','The PR result is INCONCLUSIVE, not REPRODUCED. No related tests or applicable verified invariants were recorded for build_features.','No verified public FAULTLINE project source URL was available, so none was invented.','','TIMED CAPTION / OPTIONAL NARRATION SCRIPT','00:00–00:08 Your tests passed. But what could your code change break? FAULTLINE ZERO: Understand the impact. Before the merge.']
t=8
for duration,title,sub in script:
    # Query evidence card occupies 66–75 seconds.
    if t==66:t=75
    report.append(f'{t//60:02d}:{t%60:02d}–{(t+duration)//60:02d}:{(t+duration)%60:02d} {title} {sub}');t+=duration
report.extend(['01:06–01:15 The actual FalkorDB read-only Cypher query returns caller/callee rows from the indexed RiskLens revision.','01:46–01:55 FAULTLINE ZERO. Graph-Native Pre-Merge Intelligence. Built with FalkorDB.'])
(OUT/'FAULTLINE_ZERO_Demo_Script.txt').write_text('\n'.join(report),encoding='utf-8')
print(json.dumps({'file':str(final),'duration':probe['format']['duration'],'width':v['width'],'height':v['height'],'codec':v['codec_name'],'bytes':final.stat().st_size}),flush=True)
