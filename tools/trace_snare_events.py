"""Read-only static trace of catch-related executable references; no live access."""
import sys,os,re,json,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(os.environ['TEMP'])/'SynthScanStaticTools'))
from tools.inspect_network_protocol import Image,DEFAULT_EXE
OUT=ROOT/'research/snare_independent_sources'

def main():
 image=Image(DEFAULT_EXE)
 terms=re.compile(rb'AuthorityPropagateQuantumSnareMarkerToParty|Tagged QT Snare marker|Failed to tag QT Snare marker|Failed tagged QT Snare marker|OnInterdictionSnareActivated|CCIGSessionAnalytics::OnInterdiction\(|OnInteridiction victim|Quantum Drive Interdicted by player|Interdiction Reached|interdictionDeviceId|InterdictionAlertEvent|CQedVisualGraphController::DetermineState|i_debug_quantum_interdiction_generator|quantumInterdictionFieldGenerator.state|Interdiction device outside of client view')
 strings=[]
 for m in re.finditer(rb'[\x20-\x7e]{6,400}\x00',image.data):
  if terms.search(m[0]):strings.append(dict(address=hex(image.base+image.pe.get_rva_from_offset(m.start())),text=m[0][:-1].decode()))
 refs=image.references({int(s['address'],16) for s in strings});functions={}
 for r in refs:
  start,end=int(r['function_start'],16),int(r['function_end'],16);functions[hex(start)]=image.disassemble(start,end)
 # Resolve Windows chained unwind entries so cold fragments are not mistaken
 # for the start of a complete callback.
 pdata=next(s for s in image.pe.sections if s.Name.rstrip(b"\0")==b".pdata").get_data()
 entries={image.base+a:(a,b,u) for a,b,u in struct.iter_unpack("<III",pdata[:len(pdata)//12*12]) if a<b}
 def root_entry(e):
  visited=set()
  while e[2] not in visited:
   visited.add(e[2]);raw=image.pe.get_data(e[2],4)
   if not raw[0]>>3&4:return e
   e=struct.unpack("<III",image.pe.get_data(e[2]+4+((raw[2]+1)&~1)*2,12))
  raise ValueError('Cyclic unwind chain')
 wanted={root_entry(entries[int(k,16)])[0] for k in functions}
 chains={}
 for a,b,u in entries.values():
  r=root_entry((a,b,u))
  if r[0] in wanted:
   start,end=image.base+a,image.base+b;functions[hex(start)]=image.disassemble(start,end);chains[hex(start)]=hex(image.base+r[0])
 for address in [0x140318a10,0x142da3880,0x144dcac30]:
  start,end=image.bounds(address);functions[hex(start)]=image.disassemble(start,end)
 def literal_at(address):
  try:
   off=image.pe.get_offset_from_rva(address-image.base);raw=image.data[off:off+400].split(b"\0",1)[0]
   if 4<=len(raw)<400 and all(32<=x<127 for x in raw):return raw.decode()
  except Exception:pass
 for rows in functions.values():
  for ins in rows:
   if ins['mnemonic']=='lea' and 'rip ' in ins['operands']:
    m=re.search(r'rip ([+-]) (0x[0-9a-f]+)',ins['operands'])
    if m:
     at=int(ins['address'],16);off=image.pe.get_offset_from_rva(at-image.base);decoded=list(image.cs.disasm(image.data[off:off+15],at,count=1));target=at+decoded[0].size+int(m[2],16)*(1 if m[1]=='+' else -1);value=literal_at(target)
     if value:ins['literal']=value
 # Annotate referenced literal strings and direct calls without treating function
 # unwind fragments as a complete call graph.
 literal={int(s['address'],16):s['text'] for s in strings}
 for instructions in functions.values():
  for ins in instructions:
   if ins['mnemonic']=='call' and ins['operands'].startswith('0x'):
    dest=int(ins['operands'],16);a,b=image.bounds(dest);ins['callee_fragment']=hex(a);ins['callee_end']=hex(b)
 report=dict(exe_sha256=hashlib.sha256(image.data).hexdigest(),strings=strings,references=refs,functions=functions,unwind_roots=chains,scope='On-disk x64 references; no process access. PE unwind fragments may omit split-function context.')
 (OUT/'catch_static_trace.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 for s in strings:
  print(s['address'],s['text'])
  for r in refs:
   if r['target']==s['address']:print('  reference',r['instruction']['address'],'function',r['function_start'],r['function_end'])
 print('Functions:',len(functions))

if __name__=='__main__':main()
