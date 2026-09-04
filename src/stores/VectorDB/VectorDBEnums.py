from enum import Enum

class VectorDBEnums(Enum):
    QDRANT = "QDRANT"
    PGVector = "PGVector"
    
    
class PGVectorIndexTypeEnums(Enum):
    HNSW = "hnsw"
    IVFFLAT = "ivfflat"
    
    
class DistanceMethodEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"
    ECULID = "eculid"


class PGVectorTableSchemeEnums(Enum):
    ID = "id"
    TEXT = "text"
    VECTOR = "vector"
    HALFVEC = "halfvec"
    METADATA = "metadata"
    CHUNK_ID = "chunkid"
    _PREFIX = "pgvector"
    
class PGVectorDistanceMethodEnums(Enum):
    COSINE = "vector_cosine_ops"  # <=>  Cosine distance 
    L2 = "vector_l2_ops"          # <-> Euclidean
    IP = "vector_ip_ops"          # <#>   Inner product / dot
    
    HALFVEC_COSINE = "halfvec_cosine_ops"
    HALFVEC_L2 = "halfvec_l2_ops"
    HALFVEC_IP = "halfvec_ip_ops"
    