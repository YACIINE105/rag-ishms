from sentence_transformers import CrossEncoder
import torch
import logging

class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model = CrossEncoder(model_name)
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CrossEncoder(model_name, device=device)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"CrossEncoderReranker loaded on: {device}")

    def rerank(self, query: str, documents: list[str], top_n: int = 5):
        pairs = [(query, doc) for doc in documents]
        scores = self.model.predict(pairs)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]
    
    
    