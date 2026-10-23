"""Inspect on-disk network code; never attach to or modify the game process.

Requires pefile and capstone, supplied through --dependency-dir when necessary.
Writes selected diagnostic strings, validated RIP-relative references, and x64
disassembly for their containing functions. No login files or keys are read.
"""
import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

DEFAULT_EXE = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Bin64\StarCitizen.exe"
TERMS = re.compile(rb"DecryptAndDecompress|SendCompressedAndEncrypted|software (?:encryption|decryption)|"
                   rb"Server FPS|[Ss]erver[Ff]rame|[Ss]erver[Dd]ebug|[Ss]erver[Ss]tats|"
                   rb"[Ss]hard[Pp]op|[Pp]layer[Cc]ount|SSLKEYLOGFILE|keylog_callback|"
                   rb"[Kk]ey[Ee]xchange|[Ee]ncryption[Kk]ey|[Ss]ession[Kk]ey|"
                   rb"CPingCalculator|pingTime|pongTime|Impossible latency|net_chan_ping_timeout")


class Image:
    def __init__(self, path):
        import pefile
        import capstone
        self.data = Path(path).read_bytes()
        self.pe = pefile.PE(data=self.data, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.section = next(s for s in self.pe.sections if s.Name.rstrip(b"\0") == b".text")
        self.text = self.section.get_data()
        self.text_va = self.base + self.section.VirtualAddress
        pdata = next(s for s in self.pe.sections if s.Name.rstrip(b"\0") == b".pdata").get_data()
        self.functions = sorted((self.base + start, self.base + end) for start, end, _ in
                                struct.iter_unpack("<III", pdata[:len(pdata)//12*12])
                                if 0 < start < end < self.pe.OPTIONAL_HEADER.SizeOfImage)
        self.starts = [start for start, _ in self.functions]
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)

    def bounds(self, address):
        index = bisect_right(self.starts, address) - 1
        if index >= 0:
            start, end = self.functions[index]
            if start <= address < end:
                return start, end
        return address, address + 128

    def disassemble(self, start, end):
        offset = start - self.text_va
        if not 0 <= offset < len(self.text):
            return []
        return [{"address": hex(i.address), "mnemonic": i.mnemonic, "operands": i.op_str}
                for i in self.cs.disasm(self.text[offset:offset+min(end-start, 65536)], start)]

    def references(self, targets):
        import capstone
        refs = []
        pattern = rb"[\x48-\x4f][\x8d\x8b][\x05\x0d\x15\x1d\x25\x2d\x35\x3d][\x00-\xff]{4}"
        for match in re.finditer(pattern, self.text):
            target = self.text_va + match.start() + 7 + struct.unpack_from("<i", match[0], 3)[0]
            if target not in targets:
                continue
            address = self.text_va + match.start()
            # Confirm an instruction boundary by decoding its actual PE function.
            start, end = self.bounds(address)
            instructions = self.disassemble(start, end)
            instruction = next((i for i in instructions if int(i["address"], 16) == address), None)
            if instruction:
                refs.append({"target": hex(target), "instruction": instruction,
                             "function_start": hex(start), "function_end": hex(end)})
        return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default=DEFAULT_EXE)
    parser.add_argument("--dependency-dir")
    parser.add_argument("--output", default="research/network_static_map.json")
    parser.add_argument("--range", action="append", default=[], dest="ranges",
                        help="Additional static VA range, e.g. 0x1414990c0:0x141499280")
    options = parser.parse_args()
    if options.dependency_dir:
        sys.path.insert(0, options.dependency_dir)
    image = Image(options.exe)
    strings = []
    for match in re.finditer(rb"[\x20-\x7e]{6,300}\x00", image.data):
        value = match[0][:-1]
        if TERMS.search(value):
            address = image.base + image.pe.get_rva_from_offset(match.start())
            strings.append({"address": hex(address), "text": value.decode("ascii")})
    refs = image.references({int(item["address"], 16) for item in strings})
    functions = {}
    for ref in refs:
        start, end = int(ref["function_start"], 16), int(ref["function_end"], 16)
        functions[hex(start)] = image.disassemble(start, end)
    for value in options.ranges:
        start, end = (int(part, 0) for part in value.split(":"))
        if not start < end <= start + 65536:
            parser.error("Each disassembly range must be between 1 and 65536 bytes")
        functions[hex(start)] = image.disassemble(start, end)
    report = {"exe_sha256": hashlib.sha256(image.data).hexdigest(), "image_base": hex(image.base),
              "strings": strings, "references": refs, "functions": functions,
              "scope": "Read-only static analysis. Addresses are not a runtime provider or decryption keys."}
    Path(options.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"strings": len(strings), "references": len(refs), "functions": len(functions),
                      "output": options.output}))


if __name__ == "__main__":
    main()
