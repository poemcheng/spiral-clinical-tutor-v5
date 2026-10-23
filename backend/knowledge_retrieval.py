"""Local LlamaIndex retrieval with deterministic Chinese/Latin lexical embeddings.

Only the chosen case is indexed. No external embedding service or student data.
"""
import hashlib,math,re
from functools import lru_cache

def vector(text):
    text=re.sub(r'\s+','',text.lower());v=[0.0]*384
    tokens=[text[i:i+2] for i in range(max(1,len(text)-1))]+re.findall(r'[a-z0-9]+',text)
    for token in tokens:
        v[int.from_bytes(hashlib.blake2b(token.encode(),digest_size=4).digest(),'big')%len(v)]+=1
    norm=math.sqrt(sum(x*x for x in v)) or 1
    return [x/norm for x in v]

@lru_cache(maxsize=128)
def build_index(case_id,source,parts):
    from llama_index.core import VectorStoreIndex
    from llama_index.core.schema import TextNode
    from llama_index.core.embeddings import BaseEmbedding
    class LocalEmbedding(BaseEmbedding):
        def _get_query_embedding(self,query):return vector(query)
        async def _aget_query_embedding(self,query):return vector(query)
        def _get_text_embedding(self,text):return vector(text)
    nodes=[TextNode(text=text,id_=f'{case_id}-c{i}',metadata={'source_file':source,'case_id':case_id,'sha256':hashlib.sha256(text.encode()).hexdigest()}) for i,text in enumerate(parts) if text.strip()]
    return VectorStoreIndex(nodes,embed_model=LocalEmbedding(model_name='local-lexical-384-v1'),show_progress=False)

def retrieve(case,query):
    # Do not put hidden teaching answers or facts from other patients into dialogue.
    parts=tuple(filter(None,(case['patient'].split('判讀重點')[0],case.get('patient_script',''))))
    source=case.get('source_file','既有案例')
    try:
        index=build_index(case['id'],source,parts)
        hits=index.as_retriever(similarity_top_k=min(3,len(parts))).retrieve(query)
        return [{'chunk_id':h.node.node_id,'source_file':source,'excerpt':h.node.text,'sha256':h.node.metadata['sha256'],'score':round(h.score or 0,5)} for h in hits],'llamaindex-local-lexical-384-v1'
    except ImportError:
        q=vector(query)
        ranked=sorted(enumerate(parts),key=lambda pair:sum(a*b for a,b in zip(q,vector(pair[1]))),reverse=True)
        return [{'chunk_id':f"{case['id']}-c{i}",'source_file':source,'excerpt':text,'sha256':hashlib.sha256(text.encode()).hexdigest()} for i,text in ranked[:3]],'local-lexical-fallback-v1'
