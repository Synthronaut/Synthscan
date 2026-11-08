"""Public, read-only UEX marketplace lookups for Finder. No account credentials."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time
from telemetry_ipc import publish_json,read_shared_json

INDEX_TTL=3600
LIST_TTL=600
RETRY=300

def load(path):
    try:return read_shared_json(path,limit=8*1024*1024)
    except (OSError,ValueError,TypeError):return {}

def numeric(value,default=0):
    try:
        result=float(value)
        return result if not isinstance(value,bool) and math.isfinite(result) else default
    except (ValueError,TypeError):return default

def rows(payload):
    if not isinstance(payload,dict) or payload.get('status')!='ok' or not isinstance(payload.get('data'),list):raise ValueError('Invalid UEX market response')
    return payload['data']

def catalog(payload,now):
    items={}
    for row in rows(payload):
        identifier=int(numeric(row.get('id_item')));name=row.get('item_name')
        if identifier<=0 or not isinstance(name,str) or not name.strip():continue
        uuid=str(row.get('item_uuid') or '').lower()
        fingerprint=hashlib.sha256((uuid+'|'+name).encode()).hexdigest()[:12]
        item=items.setdefault(str(identifier),dict(id=identifier,name=name,uuid=uuid,identity=fingerprint,averages=[]))
        if item['identity']!=fingerprint:raise ValueError('Ambiguous UEX market identity')
        if row.get('operation') in ('buy','sell') and row.get('currency','').upper()=='UEC':item['averages'].append(row)
    if not items:raise ValueError('Empty UEX market index')
    return dict(schema=1,checked_at=now,items=items)

def fetch_catalog():
    from item_directory import uex_json
    return catalog(uex_json('marketplace_prices_averages_all'),time.time())

def listings(payload,identifier,operation,now):
    result=[];seen=set()
    raw=rows(payload)
    for row in raw:
        if int(numeric(row.get('id_item')))!=identifier:raise ValueError('UEX returned another market item')
        if row.get('operation')!=operation or row.get('type') not in (None,'item'):continue
        if row.get('currency','').upper()!='UEC' or numeric(row.get('is_sold_out')):continue
        expiry=numeric(row.get('date_expiration'))
        if expiry and expiry<=now:continue
        price=numeric(row.get('price'));slug=row.get('slug','');identifier_row=int(numeric(row.get('id')))
        if price<=0 or identifier_row<=0 or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',slug) or identifier_row in seen:continue
        seen.add(identifier_row);quality=numeric(row.get('quality'),-1)
        renewed=max(numeric(row.get('date_added')),numeric(row.get('date_approved')))
        result.append(dict(id=identifier_row,operation=operation,price=price,unit=str(row.get('unit') or 'unspecified'),
            quality=quality if 1<quality<=1000 else None,title=str(row.get('title') or ''),location=str(row.get('location') or ''),
            renewed=renewed,url='https://uexcorp.space/marketplace/item/info/'+slug+'/'))
    return result,len(raw)>=1000

def fetch_listings(identifier):
    from item_directory import uex_json
    now=time.time();result=[];limited=False
    for operation in ('sell','buy'):
        parsed,cap=listings(uex_json(f'marketplace_listings?id_item={identifier}&operation={operation}'),identifier,operation,now)
        result+=parsed;limited|=cap
    return dict(schema=1,item=identifier,checked_at=now,rows=result,limited=limited)

def directory_rows(directory):
    data=load(Path(directory)/'finder_market_index.json');result=[]
    for item in data.get('items',{}).values():
        identifier=f"market-{item['id']}-{item['identity']}"
        result.append(dict(id=identifier,item_id=identifier,name=item['name'],kind='Market item',category='Player market',
            detail='UEX player marketplace item. Select Player market in Finder for offers and quality filters.',icon='',
            search=item['name'],market_item_id=item['id'],market_identity=item['identity'],market_uuid=item['uuid'],finder_blueprints=[]))
    return result

def enrich_directory(value,market_rows,qualities=None):
    by_uuid={};ambiguous=set();used=set()
    for row in market_rows:
        key=row['market_uuid']
        if not key:continue
        if key in by_uuid and by_uuid[key]['market_item_id']!=row['market_item_id']:ambiguous.add(key)
        by_uuid[key]=row
    for key in ambiguous:by_uuid.pop(key,None)
    for row in value['rows']:
        market=by_uuid.get(str(row.get('item_id','')).lower())
        if market:
            row.update({key:market[key] for key in ('market_item_id','market_identity')})
            if row['kind']=='Blueprint':continue
            used.add(market['market_item_id'])
            row['search']+=' '+market['name']
    for market in market_rows:
        if market['market_item_id'] not in used:value['rows'].append(market)
    for row in value['rows']:
        if qualities:
            from material_qualities import lookup
            quality=lookup(qualities,row['name'])
            if quality:row.update(quality_values=quality['values'],quality_build=qualities['build'].get('RequestedP4ChangeNum'),quality_name=quality['name'])
        board=re.search(r'\bDCHS-0([1-7])\b',row['name'],re.I)
        if board:
            row['market_board']=int(board[1]);row['search']+=f' comp{board[1]} compboard{board[1]} comp {board[1]}'
    value['rows'].sort(key=lambda row:(row['name'].casefold(),row['id']))
    return value

def comparable_prices(offers,quality_specific=True):
    """Keep raw advertisements; isolate ambiguous grades and gross price outliers."""
    groups={};warnings={}
    for offer in offers:
        grades={int(a or b) for a,b in re.findall(r'(?i)(?<![a-z0-9])Q\s*(\d{3,4})(?!\d)|(\d{3,4})\s*Q(?![a-z])',offer['title'])}
        if quality_specific and len(grades)>1:
            warnings[offer['id']]='multiple qualities advertised; price may apply to another grade'
            continue
        groups.setdefault((offer['unit'],offer['quality']),[]).append(offer)
    for group in groups.values():
        if len(group)<5:continue
        median=statistics.median(offer['price'] for offer in group)
        for offer in group:
            if offer['price']<median/20 or offer['price']>median*20:
                warnings[offer['id']]='unusually '+('low' if offer['price']<median else 'high')+' versus comparable ads; verify seller price'
    return [offer for offer in offers if offer['id'] not in warnings],warnings

def typical_range(prices):
    values=sorted(prices)
    def percentile(fraction):
        position=(len(values)-1)*fraction;lower=int(position);upper=min(lower+1,len(values)-1)
        return values[lower]+(values[upper]-values[lower])*(position-lower)
    return percentile(.25),percentile(.75),statistics.median(values)

def market_view(item,cached,minimum,patch,now,error='',exact=False):
    from item_directory import date
    output=['PLAYER MARKET — UEX Corp'];links=[]
    if not item:return dict(text='PLAYER MARKET\nNo exact UEX marketplace identity is recorded for this item.',links=[])
    output+=['Any quality' if minimum==0 else f'Quality {minimum}'+(' exactly' if exact else '–1000')+'; unspecified quality excluded',
             'Active advertisements renewed within 30 days. Prices are offers, not completed-sale values.']
    if not cached:output.append('Checking player offers in the background…' if not error else 'Market unavailable; retrying automatically.')
    else:
        age=now-cached.get('checked_at',0);output.append('Last checked: '+date(cached.get('checked_at'))+(' · cached / refresh overdue' if age>=LIST_TTL or error else ''))
        eligible=[r for r in cached.get('rows',[]) if r['renewed']>=now-30*86400 and (not minimum or r['quality'] is not None and (r['quality']==minimum if exact else r['quality']>=minimum))]
        for operation,title in [('sell','SELLERS — ASKING PRICES'),('buy','BUYERS — BUY REQUESTS')]:
            output+=['',title];offers=[r for r in eligible if r['operation']==operation]
            offers.sort(key=lambda r:(r['price'] if operation=='sell' else -r['price'],-r['renewed']))
            comparable,warnings=comparable_prices(offers,bool(minimum))
            groups=sorted({(r['unit'],r['quality'] if not minimum else None) for r in comparable},key=lambda key:(key[0],key[1] or -1))
            for unit,quality in groups:
                prices=[r['price'] for r in comparable if r['unit']==unit and (minimum or r['quality']==quality)]
                grade='' if minimum else ' · '+('quality unspecified' if quality is None else 'Q'+str(int(quality)))
                if len(prices)>=5:
                    low,high,median=typical_range(prices)
                    output.append(f'Typical {"asks" if operation=="sell" else "bids"}: {low:,.0f}–{high:,.0f} aUEC / {unit}{grade}')
                    output.append(f'Median {median:,.0f} · {len(prices)} comparable ads · range is middle 50%')
                else:output.append(f'No reliable estimate for {unit}{grade}: only {len(prices)} comparable ads; at least 5 required.')
            if not offers:output.append('No matching recent advertisements.')
            if not comparable and offers:output.append('No reliable estimate: all matching advertisements failed the price/quality checks.')
            if warnings:output.append(f'{len(warnings)} implausible-price or mixed-quality ads rejected; excluded from all estimates and results.')
            displayed=comparable[:10]
            if len(comparable)>10:output.append(f'Showing 10 of {len(comparable)} comparable advertisements; browse UEX for the rest.')
            for offer in displayed:
                quality='quality unspecified' if offer['quality'] is None else 'Q'+str(int(offer['quality']))
                output.append(f"{offer['price']:,.0f} aUEC / {offer['unit']} · {quality}")
                output.append(offer['title'][:180]+(' · '+offer['location'][:120] if offer['location'] else ''))
                label=f"Open listing #{offer['id']} · updated {date(offer['renewed'])}"
                output.append(label);links.append(dict(label=label,url=offer['url']))
        if cached.get('limited'):output.append('UEX reached its per-side listing limit; this is a partial view.')
        output.append('Listing patch is not supplied by UEX; the age filter reduces older reports.')
    # UEX aggregate averages cannot be cleaned of individual bad advertisements.
    # Use that feed only for item discovery, never as a price fallback.
    if error:output.append('Refresh unavailable; retained cached data is shown above.')
    return dict(text='\n'.join(output),links=links)

class FinderMarketService:
    def __init__(self,directory,owner,index_fetch=fetch_catalog,listing_fetch=fetch_listings):
        self.directory=Path(directory);self.owner=owner;self.index_fetch=index_fetch;self.listing_fetch=listing_fetch
        self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='finder-market');self.index=load(self.directory/'finder_market_index.json');self.job_identity=None
        self.index_due=self.index.get('checked_at',0)+INDEX_TTL;self.index_job=None;self.job=None;self.job_id=None
        self.cache={};self.retry={};self.errors={};self.active=None;self.last=None;self.next_poll=0
    def tick(self,now=None,current_patch=''):
        now=time.time() if now is None else now
        if now<self.next_poll:return
        self.next_poll=now+.25
        if self.index_job is not None and self.index_job.done():
            try:
                fresh=self.index_job.result()
                if fresh.get('schema')!=1 or not fresh.get('items'):raise ValueError('Invalid market catalog')
                if not publish_json(self.directory/'finder_market_index.json',fresh):raise OSError('Market catalog unavailable')
                self.index=fresh;self.index_due=now+INDEX_TTL
            except Exception:self.index_due=now+RETRY
            self.index_job=None
        if self.index_job is None and now>=self.index_due:self.index_job=self.pool.submit(self.index_fetch)
        request=load(self.directory/'finder_market_request.json')
        if request.get('owner_pid')==self.owner and 0<=now-numeric(request.get('at'))<60 and request.get('request_id') and request.get('row_id'):
            minimum=request.get('quality_min',0)
            if isinstance(minimum,int) and not isinstance(minimum,bool) and 0<=minimum<=1000:self.active=request
        if self.job is not None and self.job.done():
            try:
                value=self.job.result()
                if value.get('item')!=self.job_id:raise ValueError('Wrong market item')
                value=dict(value,identity=self.job_identity)
                self.cache[self.job_id]=value;folder=self.directory/'finder_market_cache';folder.mkdir(exist_ok=True)
                publish_json(folder/(str(self.job_id)+'.json'),value);self.errors.pop(self.job_id,None)
            except Exception:self.retry[self.job_id]=now+RETRY;self.errors[self.job_id]='unavailable'
            self.job=None
        if not self.active:return
        request=self.active;identifier=int(numeric(request.get('market_item_id')));item=self.index.get('items',{}).get(str(identifier))
        if item and item['identity']!=request.get('market_identity'):item=None
        if identifier not in self.cache:
            cached=load(self.directory/'finder_market_cache'/(str(identifier)+'.json'))
            self.cache[identifier]=cached if cached.get('item')==identifier else None
        cached=self.cache[identifier]
        if item and cached and cached.get('identity')!=item['identity']:cached=None
        if item and self.job is None and (not cached or now-cached.get('checked_at',0)>=LIST_TTL) and now>=self.retry.get(identifier,0):
            self.job_id=identifier;self.job_identity=item['identity'];self.job=self.pool.submit(self.listing_fetch,identifier)
        exact=request.get('quality_exact') is True
        view=market_view(item,cached,request['quality_min'],current_patch,now,self.errors.get(identifier,''),exact)
        loading=bool((item and (not cached or not 0<=now-cached.get('checked_at',0)<LIST_TTL) and not self.errors.get(identifier))
                     or (not item and self.index_job is not None))
        result=dict(owner_pid=self.owner,request_id=request['request_id'],row_id=request['row_id'],item_id=request['item_id'],quality_min=request['quality_min'],quality_exact=exact,loading=loading,error=bool(self.errors.get(identifier)),**view)
        if result!=self.last:publish_json(self.directory/'finder_market_detail.json',result);self.last=result
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
