"""Read-only Polygon JSON-RPC probe helpers (public endpoints only)."""
import json, time, urllib.request, sys
from eth_hash.auto import keccak
UA = "pmbook/0.0.1 research; github.com/thanatchon36/pmbook"
RPC = "https://polygon.drpc.org"
def rpc(method, params, url=RPC):
    for i in range(5):
        req = urllib.request.Request(url, data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
              headers={"content-type":"application/json","user-agent":UA})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            print("rpc err", repr(e)[:200], file=sys.stderr)
            time.sleep(2**i); continue
        if "error" in r: return r
        return r["result"]
    raise RuntimeError("rpc failed")
def topic(sig): return "0x" + keccak(sig.encode()).hex()
def block_ts(n): return int(rpc("eth_getBlockByNumber",[hex(n),False])["timestamp"],16)
def block_at(ts):
    hi = int(rpc("eth_blockNumber",[]),16); lo = hi - 60_000_000
    while lo < hi:
        mid = (lo+hi)//2
        if block_ts(mid) < ts: lo = mid+1
        else: hi = mid
    return lo
