#!/usr/bin/env python3
"""Extract article publication metadata from official HTML for human review only."""
import datetime as dt
import html.parser
import json
import pathlib
import re
import urllib.parse
import urllib.request

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

class Metadata(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!="meta":return
        a=dict(attrs)
        key=a.get("property") or a.get("name")
        if key and a.get("content"):self.meta[key.lower()]=a["content"]

def parse_date(value):
    if not value:return None
    try:
        stamp=dt.datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        if stamp.tzinfo is None:return None
        return stamp.isoformat()
    except (ValueError,TypeError):return None

def extract_metadata(html):
    parser=Metadata()
    parser.feed(html)
    m=parser.meta
    for key in ("article:published_time","datepublished","date","pubdate"):
        date=parse_date(m.get(key))
        if date:return {"publishedAt":date,"dateSource":key}
    for match in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.I|re.S):
        try:
            obj=json.loads(match[1])
            candidates=obj if isinstance(obj,list) else [obj]
            for entry in candidates:
                if isinstance(entry,dict):
                    date=parse_date(entry.get("datePublished"))
                    if date:return {"publishedAt":date,"dateSource":"jsonld.datePublished"}
        except (ValueError,TypeError):continue
    return {"publishedAt":None,"dateSource":"UNVERIFIED"}

def fetch_official(url,expected_index):
    a=urllib.parse.urlparse(url)
    b=urllib.parse.urlparse(expected_index)
    if a.scheme!="https" or a.hostname!=b.hostname or not a.path.startswith("/news/"):
        raise ValueError("Not an approved official team news URL")
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-Research/1.0"})
    with urllib.request.urlopen(req,timeout=10) as response:
        final=urllib.parse.urlparse(response.url)
        if final.scheme!="https" or final.hostname!=b.hostname or not final.path.startswith("/news/"):
            raise ValueError("Unexpected article redirect")
        return response.read(500000).decode("utf-8","replace")

def collect(discovery,ranked,fetch=fetch_official,limit_per_team=2):
    teams={t["team"]:t for t in discovery["teams"]}
    results=[]
    for item in ranked["items"]:
        source=teams.get(item["team"],{})
        for link in item["rankedLinks"][:limit_per_team]:
            result={"gameId":item["gameId"],"team":item["team"],"url":link["url"],
                    "status":"UNVERIFIED_ARTICLE_METADATA_FOR_HUMAN_REVIEW","starterConfirmed":False}
            try:
                page=fetch(link["url"],source["officialNewsIndex"])
                result.update(extract_metadata(page))
                result["fetchStatus"]="OK"
            except Exception as exc:
                result.update({"fetchStatus":"ERROR","publishedAt":None,"dateSource":"UNVERIFIED","error":str(exc)[:160]})
            results.append(result)
    return {"status":"METADATA_ONLY_NOT_STARTER_CONFIRMATION","automaticConfirmations":0,"items":results}

def main():
    discovery=json.loads((DATA/"model-c-official-qb-discovery.json").read_text())
    ranked=json.loads((DATA/"model-c-qb-ranked-news.json").read_text())
    output=collect(discovery,ranked)
    (DATA/"model-c-official-article-metadata.json").write_text(json.dumps(output,indent=2)+"\n")
    print("Official article metadata:",len(output["items"]),"review-only entries")

if __name__=="__main__":main()
