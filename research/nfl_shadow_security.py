"""Strict bounded transport and ZIP parsing for draft-only research artifact replay."""
import io
import urllib.parse
import urllib.request
import zipfile

MAX_DOWNLOAD=25_000_000
MAX_MEMBER=10_000_000
MAX_MEMBERS=50
TRUSTED_SUFFIXES=(".actions.githubusercontent.com",".blob.core.windows.net",".githubusercontent.com")

def trusted_redirect(url):
    u=urllib.parse.urlsplit(url)
    host=(u.hostname or "").lower()
    return (u.scheme=="https" and u.username is None and u.password is None
            and u.port in (None,443) and bool(host)
            and any(host.endswith(s) and len(host)>len(s) for s in TRUSTED_SUFFIXES))

class SafeArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not trusted_redirect(newurl):
            raise ValueError("UNTRUSTED_ARTIFACT_REDIRECT")
        return urllib.request.Request(newurl,headers={"User-Agent":"ForecastEdge-research-only-replay"})

def bounded_read(response,limit=MAX_DOWNLOAD):
    length=response.headers.get("Content-Length")
    if length is not None and int(length)>limit:
        raise ValueError("DOWNLOAD_TOO_LARGE")
    parts=[]
    total=0
    while True:
        chunk=response.read(min(65536,limit-total+1))
        if not chunk:break
        total+=len(chunk)
        if total>limit:raise ValueError("DOWNLOAD_TOO_LARGE")
        parts.append(chunk)
    return b"".join(parts)

def read_zip_members(data,required):
    if len(data)>MAX_DOWNLOAD:raise ValueError("DOWNLOAD_TOO_LARGE")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos=z.infolist()
            names=[i.filename for i in infos]
            if len(infos)>MAX_MEMBERS or len(names)!=len(set(names)):
                raise ValueError("UNSAFE_ZIP_STRUCTURE")
            if not set(required).issubset(names):
                raise ValueError("ARTIFACT_MEMBER_MISSING")
            for info in infos:
                if info.is_dir() or info.file_size>MAX_MEMBER or info.compress_size>MAX_DOWNLOAD:
                    raise ValueError("UNSAFE_ZIP_STRUCTURE")
                if info.filename.startswith("/") or "\\" in info.filename or ".." in info.filename.split("/"):
                    raise ValueError("UNSAFE_ZIP_STRUCTURE")
            return {name:z.read(name) for name in required}
    except (zipfile.BadZipFile,RuntimeError,EOFError) as exc:
        raise ValueError("INVALID_ZIP") from exc
