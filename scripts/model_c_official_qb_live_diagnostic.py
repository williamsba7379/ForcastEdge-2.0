#!/usr/bin/env python3
"""Read-only official NFL QB source transport diagnostic; never confirms a starter.

Only retrieves explicitly supplied official NFL HTTPS article URLs. No model writes.
"""
import argparse
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from model_c_official_qb_source_intake import official_url

MAX_BYTES=256000
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError("REDIRECT_BLOCKED")

def retrieve(url, opener=None):
    if not official_url(url):return {"status":"UNTRUSTED_URL"}
    opener=opener or urllib.request.build_opener(NoRedirect,urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-QB-Evidence-Diagnostic/1.0","Accept":"text/html"})
    try:
        with opener.open(req,timeout=12) as response:
            final_url=response.geturl()
            if not official_url(final_url) or urlsplit(final_url).hostname!=urlsplit(url).hostname:
                return {"status":"UNTRUSTED_FINAL_URL"}
            content_type=response.headers.get("Content-Type","").lower().split(";")[0].strip()
            if content_type!="text/html":return {"status":"UNSUPPORTED_CONTENT_TYPE"}
            body=response.read(MAX_BYTES+1)
            if len(body)>MAX_BYTES:return {"status":"OVERSIZED_CONTENT"}
            decoded=body.decode("utf-8",errors="replace")
            # Source publication metadata is untrusted until manually cross-checked.
            dates=re.findall(r'<meta[^>]+(?:article:published_time|datePublished)[^>]+>',decoded,re.I)[:3]
            return {"status":"FETCHED_REVIEW_REQUIRED","sha256":hashlib.sha256(body).hexdigest(),
                    "bytes":len(body),"publicationMetadataTags":len(dates),
                    "note":"No player name or starter status inferred; manual game-specific review required"}
    except (urllib.error.URLError,ValueError,TimeoutError,OSError) as exc:
        return {"status":"FETCH_FAILED_CLOSED","errorType":type(exc).__name__}

def fixtures():
    assert retrieve("https://nfl.com.evil.example/news/x")["status"]=="UNTRUSTED_URL"
    assert retrieve("http://www.nfl.com/news/x")["status"]=="UNTRUSTED_URL"
    class Response:
        def __init__(self,url,content_type,data):self.url=url;self.headers={"Content-Type":content_type};self.data=data
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def geturl(self):return self.url
        def read(self,n):return self.data[:n]
    class Opener:
        def __init__(self,response):self.response=response
        def open(self,*args,**kwargs):return self.response
    url="https://www.nfl.com/news/test"
    result=retrieve(url,Opener(Response(url,"text/html",b"<html>fixture</html>")))
    assert result["status"]=="FETCHED_REVIEW_REQUIRED" and "fixture" not in json.dumps(result)
    assert retrieve(url,Opener(Response("https://evil.example/a","text/html",b"x")))["status"]=="UNTRUSTED_FINAL_URL"
    assert retrieve(url,Opener(Response(url,"application/json",b"{}")))["status"]=="UNSUPPORTED_CONTENT_TYPE"
    assert retrieve(url,Opener(Response(url,"text/html",b"x"*(MAX_BYTES+1))))["status"]=="OVERSIZED_CONTENT"
    class Fail:
        def open(self,*args,**kwargs):raise urllib.error.URLError("fixture")
    assert retrieve(url,Fail())["status"]=="FETCH_FAILED_CLOSED"
    try:
        NoRedirect().redirect_request(None,None,302,"redirect",{},"https://evil.example")
    except ValueError as exc:
        assert str(exc)=="REDIRECT_BLOCKED"
    else:
        raise AssertionError("Redirect was not blocked")
    print("PASS: strict HTTPS host, no redirects, final URL, content type, size bound, fail-closed transport, no starter inference")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",help="Explicit official NFL article URL (never supplied by fixtures)")
    args=parser.parse_args()
    fixtures()
    if args.url:print("Official NFL source diagnostic:",json.dumps(retrieve(args.url),sort_keys=True))
    else:print("READ_ONLY: offline fixtures only; supply explicit --url for a bounded live fetch")
