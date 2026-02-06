import numpy as np
from fastembed import TextEmbedding
from rapidfuzz import process, fuzz
import logging

logger = logging.getLogger(__name__)

class AlignerPool:
    def __init__(self, lexical_threshold: float, semantic_threshold: float):
        self.__vectors_list: list[np.ndarray] =[]
        self.__phrases: list[str] = []
        
        self.__vector_matrix: np.ndarray | None = None
        self.__is_dirty: bool = False 
        
        self.__lexical_threshold = lexical_threshold
        self.__semantic_threshold = semantic_threshold

    def add(self, model: TextEmbedding, phrase: str):
        pharse_vector = list(model.embed([phrase]))[0]  # Extract first element to get (384,) shape
        self.__phrases.append(phrase)
        self.__vectors_list.append(np.array(pharse_vector)) 
        self.__is_dirty = True

    def __rebuild_matrix(self):
        if self.__vectors_list:
            self.__vector_matrix = np.vstack(self.__vectors_list)
        else:
            self.__vector_matrix = np.array()
        self.__is_dirty = False

    def match(self, model: TextEmbedding, query: str) -> str | None:
        if query in self.__phrases:
            return query
        
        match_tuple = process.extractOne(
            query, 
            self.__phrases, 
            scorer=fuzz.ratio
        )
        
        if match_tuple:
            matched_str, score, _ = match_tuple
            if score >= self.__lexical_threshold:
                return matched_str
        
        if self.__is_dirty:
            self.__rebuild_matrix()
            
        if len(self.__vector_matrix) == 0:
            return None

        query_embedding_gen = model.embed([query])
        query_vector = list(query_embedding_gen)[0]  # Extract first element to get (384,) shape
        
        scores = np.dot(self.__vector_matrix, query_vector)
        best_match_idx = np.argmax(scores)
        best_score = scores[best_match_idx]
        logger.info(f"Best match for {query}: {self.__phrases[best_match_idx]} with score {best_score}")
        if best_score >= self.__semantic_threshold:
            return self.__phrases[best_match_idx]
        
        return None

class Aligner:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", 
                 threads = 1):
        self.model = TextEmbedding(model_name=model_name, threads=threads)
        self.__pools: dict[str, AlignerPool] = {}

    def create_pool(self, name: str, lexical_threshold: float = 90.0, semantic_threshold: float = 0.75,) -> AlignerPool:
        if name in self.__pools:
            raise RuntimeError(f"Pool {name} already exists!")
        self.__pools[name] = AlignerPool(lexical_threshold, semantic_threshold)
        return self.__pools[name]

    def get_pool(self, name: str) -> AlignerPool:
        if name not in self.__pools:
            raise RuntimeError(f"Pool {name} does not exist!")
        return self.__pools[name]

    def add_phrase(self, pool_name: str, phrase: str):
        if pool_name not in self.__pools:
            raise RuntimeError(f"Pool {pool_name} does not exist!")
            
        # Compute embedding once at ingestion time
        embedding_gen = self.model.embed([phrase])
        vector = list(embedding_gen)
        
        self.__pools[pool_name].add(phrase, vector)
    
    def match(self, pool_name: str, query: str) -> str | None:
        if pool_name not in self.__pools:
            raise RuntimeError(f"Pool {pool_name} does not exist!")
        return self.__pools[pool_name].match(self.model, query)
    

