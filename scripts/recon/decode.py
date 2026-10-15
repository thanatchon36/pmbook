"""Decode sample exchange fills and reconcile with the Data API (read-only)."""
import json, sys, time, urllib.request
from rpc import rpc, UA
OF1='0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6'
OF2='0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee'
OM1='0x63bf4d16b7fa898ef4c4b2b6d90fd201e9c56313b65638af6088d149d2ce956c'
OM2='0x174b3811690657c217184f89418266767c87e4805d09680c39fc9c031c0cab7c'
FC='0x55bb3cade9d43b798a4fe5ffdd05024b2d7870df53920673bfc7e68047cd0ab1'
EX={'0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e':'v1','0xc5d563a36ae78145c45a50134d48a1215220f80a':'v1nr','0xe111180000d2663c0091e4f400237545b87b996b':'v2','0xe2222d279d744050d28e00520010520000310f59':'v2nr','0xe3333700ca9d93003f00f0f71f8515005f6c00aa':'x3'}
def words(d): d=d[2:]; return [int(d[i:i+64],16) for i in range(0,len(d),64)]
def addr(t): return '0x'+t[-40:]
def get(url):
    time.sleep(0.6)
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'user-agent':UA}),timeout=30))
def decode_tx(h):
    rc=rpc('eth_getTransactionReceipt',[h]); rows=[]
    for l in rc['logs']:
        a=l['address'].lower(); t0=l['topics'][0]
        if a not in EX: continue
        w=words(l['data'])
        if t0==OF1:
            mA,tA,mF,tF,fee=w[:5]
            # assetId 0 = collateral. maker gives makerAsset, receives takerAsset.
            if mA==0: side='BUY'; tok=tA; usdc=mF; sh=tF
            else: side='SELL'; tok=mA; usdc=tF; sh=mF
            rows.append(dict(ev='OrderFilled',ex=EX[a],maker=addr(l['topics'][2]),taker=addr(l['topics'][3]),maker_side=side,token=str(tok),shares=sh/1e6,usdc=usdc/1e6,price=round(usdc/sh,6) if sh else None,fee=fee/1e6,li=int(l['logIndex'],16)))
        elif t0==OF2:
            side,tok,mF,tF,fee=w[:5]
            s='BUY' if side==0 else 'SELL'
            usdc,sh=(mF,tF) if s=='BUY' else (tF,mF)
            rows.append(dict(ev='OrderFilled',ex=EX[a],maker=addr(l['topics'][2]),taker=addr(l['topics'][3]),maker_side=s,token=str(tok),shares=sh/1e6,usdc=usdc/1e6,price=round(usdc/sh,6) if sh else None,fee=fee/1e6,builder=hex(w[5]),li=int(l['logIndex'],16)))
        elif t0 in (OM1,OM2):
            rows.append(dict(ev='OrdersMatched',ex=EX[a],taker_order_maker=addr(l['topics'][2]),raw=[str(x) for x in w],li=int(l['logIndex'],16)))
        elif t0==FC:
            rows.append(dict(ev='FeeCharged',ex=EX[a],receiver=addr(l['topics'][1]),amount=w[0]/1e6,li=int(l['logIndex'],16)))
    return int(rc['blockNumber'],16), rows
if __name__=='__main__':
    h=sys.argv[1]; b,rows=decode_tx(h)
    print('tx',h,'block',b)
    for r in rows: print(' ',json.dumps(r))
