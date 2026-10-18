"""Remove the editorial chapter guide and finish narration loudness."""
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/demo';EDIT=OUT/'premium'
FF=r'C:\Users\Enosh\AppData\Roaming\Python\Python314\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
FP=r'C:\Users\Enosh\Downloads\krita-x64-5.3.3\krita-x64-5.3.3\bin\ffprobe.exe'
yy,xx=np.mgrid[0:270,0:480];r=np.exp(-(((xx-240)/170)**2+((yy-205)/85)**2));bg=np.zeros((270,480,3),dtype=np.uint8)
for c,(a,b) in enumerate([(5,11),(10,30),(8,18)]):bg[:,:,c]=a+(r*b).astype(np.uint8)
base=Image.fromarray(bg).resize((1920,1080),Image.Resampling.BICUBIC).convert('RGBA');d=ImageDraw.Draw(base)
for x in range(36,1920,72):
 for y in range(30,1080,72):d.ellipse((x,y,x+1,y+1),fill=(90,132,107,32))
base.convert('RGB').crop((0,997,1920,1080)).save(EDIT/'clean-footer.png')
source=OUT/'FAULTLINE_ZERO_Hackathon_Demo_Premium.mp4';final=OUT/'FAULTLINE_ZERO_Final_Narrated.mp4'
subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(source),'-loop','1','-i',str(EDIT/'clean-footer.png'),'-filter_complex_threads','1','-filter_complex','[1:v]format=rgb24,fade=t=out:st=104.3:d=0.7[footer];[0:v][footer]overlay=0:997:shortest=1[v]','-map','[v]','-map','0:a:0','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','4','-c:a','aac','-b:a','192k','-ar','48000','-t','105','-metadata','title=FAULTLINE ZERO — Graph-Native Pre-Merge Intelligence','-metadata','comment=Real software footage, English synthetic narration, burned-in synchronized captions, original score.','-movflags','+faststart',str(final)],check=True)
probe=json.loads(subprocess.check_output([FP,'-v','error','-show_streams','-show_format','-of','json',str(final)],text=True))
v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['codec_name'],a['codec_name'])==(1920,1080,'h264','aac')
assert 104.9<float(probe['format']['duration'])<105.1
subprocess.run([FF,'-v','error','-i',str(final),'-f','null','-'],check=True)
(OUT/'final-narrated-verification.json').write_text(json.dumps(probe,indent=2))
script=OUT/'FAULTLINE_ZERO_Premium_Script.txt'
script.write_text(script.read_text().replace('Licensed platform neural voice','Synthetic neural voice').replace('chapter rail, ','')+'\nFinal delivery: FAULTLINE_ZERO_Final_Narrated.mp4. Editorial chapter guide removed; narration normalized to -16 LUFS target.\n',encoding='utf-8')
# Sample the finished export, not a mock-up.
times=[1,4,6,11,16,22,28,33,39,47,53,60,69,77,86,93,100]
sheet=Image.new('RGB',(1280,202*((len(times)+2)//3)),'#1a1a1a');d=ImageDraw.Draw(sheet)
import io
for i,t in enumerate(times):
 b=subprocess.check_output([FF,'-v','error','-ss',str(t),'-i',str(final),'-frames:v','1','-f','image2pipe','-c:v','png','-threads','1','-'])
 im=Image.open(io.BytesIO(b));im.thumbnail((426,180));x=i%3*426;y=i//3*202;sheet.paste(im,(x,y+20));d.text((x+5,y+3),str(t)+' sec',fill='white')
 if t in [39,60,86]:Image.open(io.BytesIO(b)).save(OUT/f'final-narrated-{t}.png')
sheet.save(OUT/'final-narrated-contact.jpg')
print(json.dumps({'final':str(final),'duration':probe['format']['duration'],'resolution':'1920x1080','audio':a['codec_name'],'size_mb':round(final.stat().st_size/1048576,2),'full_decode':'passed'}),flush=True)
