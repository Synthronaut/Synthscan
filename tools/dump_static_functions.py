"""Dump complete chained-unwind groups from an on-disk PE for local research."""
import os,sys,re,struct,json,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(os.environ['TEMP'])/'SynthScanStaticTools'))
from tools.inspect_network_protocol import Image,DEFAULT_EXE

def main():
 p=argparse.ArgumentParser();p.add_argument('--addresses',nargs='+',required=True);p.add_argument('--output',required=True);args=p.parse_args();im=Image(DEFAULT_EXE)
 pdata=next(s for s in im.pe.sections if s.Name.rstrip(b'\0')==b'.pdata').get_data();entries={im.base+a:(a,b,u) for a,b,u in struct.iter_unpack('<III',pdata[:len(pdata)//12*12]) if a<b}
 def root(e):
  visited=set()
  while e[2] not in visited:
   visited.add(e[2]);u=im.pe.get_data(e[2],4)
   if not u[0]>>3&4:return e[0]
   e=struct.unpack('<III',im.pe.get_data(e[2]+4+((u[2]+1)&~1)*2,12))
  raise ValueError('Cyclic unwind chain')
 wanted={root(entries[im.bounds(int(a,0))[0]]) for a in args.addresses if im.bounds(int(a,0))[0] in entries};functions={};literals=[]
 for value in args.addresses:
  a,b=im.bounds(int(value,0))
  if a not in entries:functions[hex(a)]=dict(root=hex(a),end=hex(b),instructions=im.disassemble(a,b),unwind_unavailable=True)
 for a,b,u in entries.values():
  parent=root((a,b,u))
  if parent not in wanted:continue
  rows=im.disassemble(im.base+a,im.base+b)
  for x in rows:
   at=int(x['address'],16);m=re.search(r'rip ([+-]) (0x[0-9a-f]+)',x['operands'])
   if m:
    off=im.pe.get_offset_from_rva(at-im.base);size=next(im.cs.disasm(im.data[off:off+15],at,count=1)).size;target=at+size+int(m[2],16)*(1 if m[1]=='+' else -1);x['rip_target']=hex(target)
    try:
     off=im.pe.get_offset_from_rva(target-im.base);raw=im.data[off:off+20000].split(b'\0',1)[0]
     if raw and len(raw)<20000 and all(v in [9,10,13] or 32<=v<127 for v in raw):x['literal']=raw.decode();literals.append(dict(at=x['address'],text=x['literal'],root=hex(im.base+parent)))
    except Exception:pass
  functions[hex(im.base+a)]=dict(root=hex(im.base+parent),end=hex(im.base+b),instructions=rows)
 Path(args.output).write_text(json.dumps(dict(exe_sha256=hashlib.sha256(im.data).hexdigest(),functions=functions,literals=literals,scope='Read-only executable disassembly; no live process access'),indent=2),encoding='utf-8')
 print(json.dumps(dict(fragments=len(functions),literals=literals[:65]),indent=2))

if __name__=='__main__':main()
