"""Validate names from game logs or saved history; no screen capture or OCR."""
import re

GENERIC={'YOUR','CURRENT','POSITION','IN','QUEUE','IS','THE','SERVER','SHARD','LOADING','CONNECTING','UNKNOWN','PLEASE','WAIT','MAIN','MENU','LOCAL','FRONTEND','TO','UNIVERSE'}
def clean_name(value):
    if not isinstance(value,str):return None
    words=value.replace('_',' ').strip().upper().split()
    if len(words)!=2 or any(not re.fullmatch(r"[A-Z][A-Z'-]{1,31}",w) or w in GENERIC for w in words):return None
    return ' '.join(words)
