"""Conservative reset hints from CIG's public Persistent Universe RSS feed."""
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re,time,urllib.request,xml.etree.ElementTree as ET

URL='https://status.robertsspaceindustries.com/affected/persistent-universe/index.xml'
RESET=re.compile(r'(?:servers?\b.{0,65}\b(?:offline|reset|restart|hotfix|updates?|maintenance)|(?:restart|reset).{0,30}\bservers?\b)',re.I)


def parse_resets(raw,now=None):
    now=time.time() if now is None else now
    if len(raw)>1048576 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Unsupported status feed')
    root=ET.fromstring(raw)
    if root.tag!='rss' or root.find('channel') is None:raise ValueError('Status feed unavailable')
    latest=0
    for item in root.findall('./channel/item')[:150]:
        html=item.findtext('description','')
        text=unescape(re.sub('<[^>]+>',' ',re.sub(r'</p>|<br\s*/?>','\n',html,flags=re.I)))
        if re.search(r'(?:not impact game connectivity|deployed without downtime)',text,re.I):continue
        if not RESET.search(text):continue
        try:published=parsedate_to_datetime(item.findtext('pubDate','')).timestamp()
        except (ValueError,TypeError,AttributeError):continue
        candidates=[published];date=datetime.fromtimestamp(published,timezone.utc).date()
        for line in text.splitlines():
            match=re.search(r'\[(\d{4}-\d{2}-\d{2}) Updates\]',line)
            if match:
                try:date=datetime.strptime(match[1],'%Y-%m-%d').date()
                except ValueError:continue
            clock=re.search(r'\b([0-2]\d)([0-5]\d) UTC\b',line)
            if clock and RESET.search(line):
                try:candidates.append(datetime(date.year,date.month,date.day,int(clock[1]),int(clock[2]),tzinfo=timezone.utc).timestamp())
                except ValueError:pass
        latest=max(latest,max((stamp for stamp in candidates if 0<stamp<=now+86400),default=0))
    return dict(ok=True,checked_at=now,latest_reset_at=latest,source=URL)


def fetch_resets():
    request=urllib.request.Request(URL,headers={'User-Agent':'SynthScan-hangar-schedule/1.0'})
    with urllib.request.urlopen(request,timeout=8) as response:raw=response.read(1048577)
    return parse_resets(raw)
