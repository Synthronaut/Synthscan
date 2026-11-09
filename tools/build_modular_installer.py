"""Build the single branded installer with all feature choices selected."""
import argparse
import json
from pathlib import Path
import sys
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import config,digest
from feature_modules import FEATURES
from module_distribution import catalog,inspect_package
from tools.build_installer import compiler

ROOT=Path(__file__).resolve().parents[1]


def artwork():
    """Render installer UI branding from the project's existing vector mark."""
    from PIL import Image,ImageDraw,ImageFont
    import io,math,resvg_py
    folder=ROOT/'installer/branding';folder.mkdir(exist_ok=True)
    mark=Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=(ROOT/'assets/branding/synthscan.svg').read_text(),width=256,height=256))).convert('RGBA')
    image=Image.new('RGB',(420,800));pixels=image.load()
    for y in range(image.height):
        for x in range(image.width):
            glow=max(0,1-math.hypot((x-210)/370,(y-210)/580))
            pixels[x,y]=(int(12+10*glow),int(18+22*glow),int(28+34*glow))
    draw=ImageDraw.Draw(image)
    for inset in (24,34):draw.rounded_rectangle((inset,inset,419-inset,799-inset),radius=20,outline=(39,65,87),width=1)
    image.paste(mark,(82,130),mark)
    font=lambda size,bold=False:ImageFont.truetype('C:/Windows/Fonts/'+('seguisb.ttf' if bold else 'segoeui.ttf'),size)
    draw.text((210,425),'SynthScan',anchor='mm',font=font(45,True),fill='#e5f5ff')
    draw.text((210,479),'YOUR VERSE, CONNECTED',anchor='mm',font=font(17),fill='#70cbf4')
    draw.line((100,537,320,537),fill='#395b74',width=1)
    for y,line in [(584,'One app.'),(620,'Your choice of features.'),(700,'COMMUNITY ALPHA')]:draw.text((210,y),line,anchor='mm',font=font(19 if y<700 else 13),fill='#b3c8dc' if y<700 else '#70a7c4')
    image.save(folder/'welcome.bmp')
    small=Image.new('RGB',(80,80),'#10151d');logo=mark.resize((72,72),Image.Resampling.LANCZOS);small.paste(logo,(4,4),logo);small.save(folder/'mark.bmp')


def build(payload,output,validation=False):
    payload=Path(payload).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    value=catalog((payload/'synthscan-modules.json').read_bytes(),config(payload/'core'))
    for name,item in value['packages'].items():inspect_package(payload/('SynthScan-module-'+name+'.zip'),item)
    include='\n'.join('Source: "{#Payload}\\SynthScan-module-'+name+'.zip"; DestDir: "{tmp}\\SynthScanComponents"; Components: '+name+'; Flags: deleteafterinstall' for name in FEATURES)+'\n'
    (payload/'installer-components.iss').write_text(include,encoding='utf-8')
    artwork()
    reserve=sum(item['unpacked_size'] for item in value['packages'].values())+128*1024*1024
    subprocess.run([str(compiler()),'/Qp',*(['/DValidationBuild=1'] if validation else []),'/DAppVersion='+value['version'],'/DSelectionReserve='+str(reserve),'/DPayload='+str(payload),'/DOutput='+str(output),str(ROOT/'installer/SynthScan-Modular.iss')],check=True)
    file=output/('SynthScan-Validation-Setup-Windows-x64.exe' if validation else 'SynthScan-Setup-Windows-x64.exe');sha=digest(file)
    file.with_suffix('.exe.sha256').write_text(sha+'  '+file.name+'\n',encoding='ascii')
    return dict(installer=str(file),sha256=sha,bytes=file.stat().st_size,version=value['version'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);parser.add_argument('--output',required=True);parser.add_argument('--validation',action='store_true');args=parser.parse_args()
    print(json.dumps(build(args.payload,args.output,args.validation),indent=2))
