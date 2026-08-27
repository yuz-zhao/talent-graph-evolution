"""Persistent local HTTP service for real BGE query embeddings."""
from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from fastembed import TextEmbedding

MODEL=os.getenv("EMBEDDING_MODEL","BAAI/bge-small-zh-v1.5")
PORT=int(os.getenv("EMBEDDING_PORT","8008"))
model=TextEmbedding(model_name=MODEL)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!="/health": return self.send_error(404)
        self.respond({"status":"ok","model":MODEL,"fake_embedding":False})
    def do_POST(self):
        if self.path!="/embed": return self.send_error(404)
        try:
            length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
            texts=payload.get("texts") or []
            if not isinstance(texts,list) or not texts or len(texts)>32: raise ValueError("texts must contain 1-32 strings")
            vectors=[[float(v) for v in x] for x in model.query_embed([str(x)[:4000] for x in texts])]
            self.respond({"model":MODEL,"dimension":len(vectors[0]),"vectors":vectors,"fake_embedding":False})
        except Exception as exc: self.respond({"error":str(exc)},400)
    def respond(self,payload,status=200):
        body=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,format,*args): pass
if __name__=="__main__":
    print(json.dumps({"service":"embedding","model":MODEL,"port":PORT,"fake_embedding":False}),flush=True); ThreadingHTTPServer(("127.0.0.1",PORT),Handler).serve_forever()
