"""Render the original SVG brand mark into PNG and Windows multi-size icons."""
from pathlib import Path
from io import BytesIO
import resvg_py
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'assets/branding'
    rendered=resvg_py.svg_to_bytes(svg_string=(folder/'synthscan.svg').read_text(encoding='utf-8'),width=512,height=512,skip_system_fonts=True)
    (folder/'synthscan.png').write_bytes(rendered)
    (folder/'synthscan-128.png').write_bytes(resvg_py.svg_to_bytes(svg_string=(folder/'synthscan.svg').read_text(encoding='utf-8'),width=128,height=128,skip_system_fonts=True))
    with Image.open(BytesIO(rendered)) as image:
        image.convert('RGBA').save(folder/'SynthScan-Blue.ico',format='ICO',sizes=[(n,n) for n in (16,20,24,32,40,48,64,96,128,256)])
    (ROOT/'native/synthscan/resources/synthscan.ico').write_bytes((folder/'SynthScan-Blue.ico').read_bytes())


if __name__=='__main__':main()
