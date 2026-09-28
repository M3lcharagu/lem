#!/usr/bin/env python3
"""Stdlib-only Deriv R_25/R_75 Hermes-style candle backtest.

Usage: python backtest/run_backtest.py [--offline [candles.json]] [--balance 10000]
Offline JSON: {"R_25":[...],"R_75":[...]}, {"candles":[...]}, or a list
(reused for both symbols). Rows use epoch/open/high/low/close; time is accepted.
Assumptions: UTC sessions, strict 2-left/2-right pivots confirmed at close,
latest unswept pivot is the level; RSI7 >=40 CALL / <=60 PUT; Wilder SAR step
.02 cap .20; close entry; stop at sweep-bar extreme with no tick buffer; TP=2R.
Risk stays 1% of starting balance; max three accepted entries per UTC day across
both symbols, one portfolio position at once. Stop wins if stop and target hit
within one bar. Unclosed trades stay open (no time exit), fees/slippage are zero.
With missing timestamps, session filter is skipped and reported; daily cap uses
synthetic 1440-row days because actual calendar dates are unavailable.
"""
import argparse, base64, hashlib, json, math, os, socket, ssl, struct, sys, time
from datetime import datetime, timezone
from urllib.parse import urlsplit
SYMBOLS=("R_25","R_75")
URL="wss://ws.derivws.com/websockets/v3?app_id=1089"
COUNT=5000
SESSIONS={(9,40),(11,40),(14,40)}

class WebSocketError(RuntimeError): pass
class WS:
    def __init__(self,url,timeout=30): self.url,self.timeout,self.sock=url,timeout,None
    def __enter__(self):
        p=urlsplit(self.url); raw=socket.create_connection((p.hostname,p.port or 443),self.timeout)
        self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=p.hostname)
        key=base64.b64encode(os.urandom(16)).decode(); path=p.path or "/"
        if p.query: path+="?"+p.query
        req=("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"%(path,p.hostname,p.port or 443,key)).encode()
        self.sock.sendall(req); h=bytearray()
        while not h.endswith(b"\r\n\r\n"):
            b=self.sock.recv(1)
            if not b: raise WebSocketError("Closed during handshake")
            h+=b
            if len(h)>65536: raise WebSocketError("Oversized handshake")
        lines=h.decode("iso-8859-1").split("\r\n")
        heads={x.split(":",1)[0].lower():x.split(":",1)[1].strip() for x in lines[1:] if ":" in x}
        accept=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if " 101 " not in (lines[0]+" ") or heads.get("sec-websocket-accept")!=accept: raise WebSocketError("WebSocket upgrade rejected")
        self.sock.settimeout(self.timeout); return self
    def exact(self,n):
        b=bytearray()
        while len(b)<n:
            x=self.sock.recv(n-len(b))
            if not x: raise WebSocketError("WebSocket closed unexpectedly")
            b+=x
        return bytes(b)
    def send(self,obj):
        data=json.dumps(obj,separators=(",",":")).encode(); n=len(data); first=b"\x81"
        hdr=first+bytes([0x80|n]) if n<126 else (first+bytes([0x80|126])+struct.pack("!H",n) if n<65536 else first+bytes([0x80|127])+struct.pack("!Q",n))
        mask=os.urandom(4); self.sock.sendall(hdr+mask+bytes(x^mask[i%4] for i,x in enumerate(data)))
    def control(self,op,payload=b""):
        m=os.urandom(4); self.sock.sendall(bytes([0x80|op,0x80|len(payload)])+m+bytes(x^m[i%4] for i,x in enumerate(payload)))
    def receive(self):
        chunks=bytearray(); msgop=None
        while True:
            a,b=self.exact(2); fin=bool(a&128); op=a&15; n=b&127
            if a&112: raise WebSocketError("Unsupported websocket extension")
            if n==126:n=struct.unpack("!H",self.exact(2))[0]
            elif n==127:n=struct.unpack("!Q",self.exact(8))[0]
            if n>16*1024*1024: raise WebSocketError("Oversized websocket frame")
            mask=self.exact(4) if b&128 else None; data=self.exact(n)
            if mask:data=bytes(x^mask[i%4] for i,x in enumerate(data))
            if op==8: raise WebSocketError("Deriv closed websocket")
            if op==9:self.control(10,data); continue
            if op==10:continue
            if op in (1,2):
                if msgop is not None:raise WebSocketError("Unexpected data frame")
                msgop=op
            elif op!=0 or msgop is None:raise WebSocketError("Unsupported websocket opcode")
            chunks+=data
            if len(chunks)>16*1024*1024:raise WebSocketError("Oversized websocket message")
            if fin:
                if msgop!=1:raise WebSocketError("Expected text JSON")
                try:return json.loads(chunks.decode())
                except (UnicodeDecodeError,json.JSONDecodeError) as e:raise WebSocketError("Invalid Deriv JSON: %s"%e)
    def close(self):
        if self.sock:
            try:self.control(8,struct.pack("!H",1000))
            except OSError:pass
            self.sock.close(); self.sock=None
    def __exit__(self,*args):self.close()

def epoch_of(v):
    if v is None or v=="":return None
    try:
        s=str(v).strip()
        if isinstance(v,(int,float)) or s.replace(".","",1).isdigit():return int(float(v))
        if s.endswith("Z"):s=s[:-1]+"+00:00"
        d=datetime.fromisoformat(s)
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return int(d.timestamp())
    except (ValueError,TypeError,OverflowError):return None

def normalize(rows):
    if isinstance(rows,dict):rows=rows.get("candles",[])
    out=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict):continue
        try:
            b={k:float(r[k]) for k in ("open","high","low","close")}
            if not all(math.isfinite(x) for x in b.values()) or b["high"]<b["low"]:continue
            if not(b["low"]<=b["open"]<=b["high"] and b["low"]<=b["close"]<=b["high"]):continue
            b["epoch"]=epoch_of(r.get("epoch",r.get("time"))); out.append(b)
        except (KeyError,TypeError,ValueError,OverflowError):continue
    if out and all(x["epoch"] is not None for x in out):
        by={x["epoch"]:x for x in sorted(out,key=lambda x:x["epoch"])}; out=[by[t] for t in sorted(by)]
    return out

def fetch(symbol,timeout):
    req={"ticks_history":symbol,"adjust_start":1,"count":min(COUNT,5000),"end":"latest","granularity":60,"style":"candles","req_id":1}
    with WS(URL,timeout) as ws:
        ws.send(req); end=time.monotonic()+timeout
        while time.monotonic()<end:
            r=ws.receive()
            if r.get("req_id") not in (None,1):continue
            if r.get("error"):
                e=r["error"]; raise RuntimeError("Deriv %s: %s"%(e.get("code","error"),e.get("message",e)))
            if r.get("msg_type")=="candles" or "candles" in r:return normalize(r.get("candles",[]))
    raise TimeoutError("Timed out waiting for %s"%symbol)

def offline(path):
    with open(path,encoding="utf-8") as f:d=json.load(f)
    return {s:normalize(d if isinstance(d,list) else d.get(s,d.get("candles",[])) if isinstance(d,dict) else []) for s in SYMBOLS}

def ema(v,p):
    a=2/(p+1); out=[None]*len(v)
    if v:
        out[0]=v[0]
        for i in range(1,len(v)):out[i]=a*v[i]+(1-a)*out[i-1]
    return out

def rsi(v,p=7):
    out=[None]*len(v)
    if len(v)<=p:return out
    gains=[max(v[i]-v[i-1],0) for i in range(1,len(v))]; losses=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
    g=sum(gains[:p])/p; l=sum(losses[:p])/p
    def val(g,l):return (100-100/(1+g/l)) if l else (100 if g else 50)
    out[p]=val(g,l)
    for i in range(p+1,len(v)):
        g=(g*(p-1)+gains[i-1])/p; l=(l*(p-1)+losses[i-1])/p; out[i]=val(g,l)
    return out

def sar(c,step=.02,cap=.20):
    n=len(c); sv=[None]*n; up=[None]*n; flip=[None]*n
    if n<2:return sv,up,flip
    bull=c[1]["close"]>=c[0]["close"]; s=min(c[0]["low"],c[1]["low"]) if bull else max(c[0]["high"],c[1]["high"])
    ep=max(c[0]["high"],c[1]["high"]) if bull else min(c[0]["low"],c[1]["low"]); af=step
    sv[1]=s; up[1]=bull; flip[1]=False
    for i in range(2,n):
        was=bull; x=s+af*(ep-s)
        if bull:
            x=min(x,c[i-1]["low"],c[i-2]["low"])
            if c[i]["low"]<x:bull=False; x=ep; ep=c[i]["low"]; af=step
            elif c[i]["high"]>ep:ep=c[i]["high"]; af=min(cap,af+step)
        else:
            x=max(x,c[i-1]["high"],c[i-2]["high"])
            if c[i]["high"]>x:bull=True; x=ep; ep=c[i]["high"]; af=step
            elif c[i]["low"]<ep:ep=c[i]["low"]; af=min(cap,af+step)
        s=x; sv[i]=s; up[i]=bull; flip[i]=bull!=was
    return sv,up,flip

def iso(t):return datetime.fromtimestamp(t,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t is not None else "UNKNOWN"
def session_ok(t):
    if t is None:return True
    d=datetime.fromtimestamp(t,tz=timezone.utc); return d.weekday()<=3 and (d.hour,d.minute) in SESSIONS

def candidates(sym,c,balance,all_timed):
    n=len(c)
    if n<52:return []
    close=[x["close"] for x in c]; e20,e50=ema(close,20),ema(close,50); rr=rsi(close); _,sar_up,flips=sar(c)
    hi=lo=None; out=[]
    for i in range(50,n):
        p=i-2
        if p>=2:
            lp=c[p-2:p]; rp=c[p+1:i+1]
            if all(c[p]["high"]>x["high"] for x in lp+rp):hi=(c[p]["high"],p)
            if all(c[p]["low"]<x["low"] for x in lp+rp):lo=(c[p]["low"],p)
        b=c[i]; bull=bear=False
        if lo and b["low"]<lo[0]:bull=b["close"]>lo[0]; lo=None
        if hi and b["high"]>hi[0]:bear=b["close"]<hi[0]; hi=None
        if bull==bear or rr[i] is None or flips[i] is not True:continue
        direction="CALL" if bull else "PUT"
        if direction=="CALL" and not(e20[i]>e50[i] and rr[i]>=40 and sar_up[i]):continue
        if direction=="PUT" and not(e20[i]<e50[i] and rr[i]<=60 and not sar_up[i]):continue
        t=b["epoch"]
        if all_timed and not session_ok(t):continue
        entry=b["close"]; stop=b["low"] if bull else b["high"]; dist=abs(entry-stop)
        if dist<=0:continue
        target=entry+(2*dist if bull else -2*dist)
        out.append({"symbol":sym,"index":i,"epoch":t,"direction":direction,"entry":entry,"stop":stop,"target":target,"dist":dist,"risk":balance*.01,"rsi":rr[i],"ema20":e20[i],"ema50":e50[i],"sar":sar_up[i]})
    return out

def resolve(sig,bars,all_timed):
    long=sig["direction"]=="CALL"; stop,target=sig["stop"],sig["target"]
    for j in range(sig["index"]+1,len(bars)):
        b=bars[j]; hs=b["low"]<=stop if long else b["high"]>=stop; ht=b["high"]>=target if long else b["low"]<=target
        if hs or ht:
            won=ht and not hs; pnl=sig["risk"]*(2 if won else -1)
            return {**sig,"status":"WIN" if won else "LOSS","pnl":pnl,"exit_epoch":b["epoch"],"exit_index":j,"exit":target if won else stop}
    return {**sig,"status":"OPEN","pnl":0.0,"exit_epoch":bars[-1]["epoch"],"exit_index":len(bars)-1,"exit":None}

def backtest(data,balance):
    all_timed=all(b["epoch"] is not None for arr in data.values() for b in arr) and any(data.values())
    pool=[]
    for s in SYMBOLS:pool+=candidates(s,data[s],balance,all_timed)
    pool.sort(key=lambda x:((x["epoch"] if all_timed else x["index"]*60),x["symbol"],x["index"]))
    accepted=[]; daily={}; busy_until=None
    for sig in pool:
        key=sig["epoch"] if all_timed else sig["index"]*60
        if busy_until is not None and key<=busy_until:continue
        day=datetime.fromtimestamp(sig["epoch"],timezone.utc).date().isoformat() if all_timed else "synthetic-%d"%(sig["index"]//1440)
        if daily.get(day,0)>=3:continue
        tr=resolve(sig,data[sig["symbol"]],all_timed)
        accepted.append(tr); daily[day]=daily.get(day,0)+1
        busy_until=(tr["exit_epoch"] if all_timed else tr["exit_index"]*60)
    closed=[t for t in accepted if t["status"]!="OPEN"]; wins=[t for t in closed if t["pnl"]>0]; losses=[t for t in closed if t["pnl"]<0]
    equity=peak=balance; dd=0.0
    for t in closed:
        equity+=t["pnl"]; peak=max(peak,equity); dd=max(dd,peak-equity)
    return {"accepted":accepted,"closed":closed,"wins":wins,"losses":losses,"balance":balance,"net":sum(t["pnl"] for t in closed),"drawdown":dd,"drawdown_pct":100*dd/peak if peak else 0,"all_timed":all_timed,"pool_count":len(pool)}

def main():
    ap=argparse.ArgumentParser(description="Hermes-style R_25/R_75 sweep backtest")
    ap.add_argument("--offline",nargs="?",const="candles.json",metavar="PATH",help="read local candle JSON; default PATH is candles.json")
    ap.add_argument("--balance",type=float,default=10000.0,help="starting balance (default 10000)")
    ap.add_argument("--timeout",type=int,default=30,help="Deriv websocket timeout seconds")
    a=ap.parse_args()
    if a.balance<=0:ap.error("--balance must be positive")
    try:
        data=offline(a.offline) if a.offline is not None else {s:fetch(s,a.timeout) for s in SYMBOLS}
        r=backtest(data,a.balance); closed=r["closed"]; wins=r["wins"]; losses=r["losses"]
        avgwin=sum(t["pnl"] for t in wins)/len(wins) if wins else 0.0
        avgloss=sum(t["pnl"] for t in losses)/len(losses) if losses else 0.0
        exp=r["net"]/len(closed) if closed else 0.0
        print("HERMES BACKTEST (UTC; stdlib only)")
        print("Source: %s"%("offline:"+a.offline if a.offline is not None else "Deriv no-auth WebSocket ticks_history"))
        print("Bars: R_25=%d R_75=%d; granularity=60s; requested_count<=5000"%(len(data["R_25"]),len(data["R_75"])))
        print("Session filter: %s"%("enabled (Mon-Thu 09:40/11:40/14:40 UTC)" if r["all_timed"] else "SKIPPED (one or more candle timestamps are missing)"))
        print("Setups accepted: %d (candidate setups before portfolio/day caps: %d)"%(len(r["accepted"]),r["pool_count"]))
        print("Closed trades: %d; open at end: %d; wins: %d; losses: %d"%(len(closed),sum(t["status"]=="OPEN" for t in r["accepted"]),len(wins),len(losses)))
        print("Win rate: %.2f%%"%(100*len(wins)/len(closed) if closed else 0.0))
        print("Net P&L: %.2f; average win: %.2f; average loss: %.2f; expectancy/trade: %.2f"%(r["net"],avgwin,avgloss,exp))
        print("Max drawdown: %.2f (%.2f%% of peak equity); starting balance: %.2f; ending closed-trade equity: %.2f"%(r["drawdown"],r["drawdown_pct"],a.balance,a.balance+r["net"]))
        print("Risk/trade: %.2f (1%% of starting balance); target: 2R; max accepted entries/day: 3"%(a.balance*.01))
        print("Assumptions: stop-first on same-candle stop/target; no time exit; fees/slippage=0.")
        print("LAST 5 HERMES CALL BLOCKS")
        for t in r["accepted"][-5:]:
            print("----- HERMES CALL BLOCK -----")
            print("symbol: %s"%t["symbol"]); print("signal: %s"%t["direction"]); print("time: %s"%iso(t["epoch"]))
            print("entry: %.8f"%t["entry"]); print("stop: %.8f"%t["stop"]); print("target: %.8f"%t["target"])
            print("risk: %.2f; risk_pct_starting_balance: 1.00%%"%t["risk"])
            print("setup: wick-through/close-back sweep; EMA20=%0.8f EMA50=%0.8f RSI7=%0.2f; SAR flip %s"%(t["ema20"],t["ema50"],t["rsi"],"bullish" if t["direction"]=="CALL" else "bearish"))
            print("result: %s; pnl: %.2f; exit_time: %s"%(t["status"],t["pnl"],iso(t["exit_epoch"])))
            print("----- END HERMES CALL BLOCK -----")
        return 0
    except (OSError,ValueError,RuntimeError,TimeoutError,WebSocketError,json.JSONDecodeError) as e:
        print("backtest error: %s"%e,file=sys.stderr); return 1
if __name__=="__main__":raise SystemExit(main())
