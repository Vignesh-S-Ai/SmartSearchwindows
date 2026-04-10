
import unittest
import math
import os
from pathlib import Path
from search.query_engine import QueryEngine
from indexer.faiss_index import FAISSIndex

class MockEmbedder:
    def embed_texts(self, texts):
        return [[0.1] * 3072 for _ in texts]

class MockBM25:
    def search(self, query, k):
        return []
    def add(self, texts, metadata):
        pass

class MockMetadataStore:
    def get_all_paths(self):
        return ["test1.txt", "test2.txt"]

class TestSearchQuality(unittest.TestCase):
    def setUp(self):
        # Use temporary paths for tests
        self.tmp_meta = "test_faiss_meta.json"
        self.tmp_index = "test_faiss_index.bin"
        
        # Initialize FAISSIndex and override paths
        self.faiss = FAISSIndex()
        self.faiss.meta_path = Path(self.tmp_meta)
        self.faiss.index_path = Path(self.tmp_index)
        self.faiss.metadata = {"chunks": {}, "paths": {}}
        
        # Mock the internal FAISS object
        import numpy as np
        class MockFaissObj:
            def IndexFlatL2(self, dim):
                class MockIndex:
                    def __init__(self): self.ntotal = 0
                    def add(self, arr): self.ntotal += len(arr)
                    def search(self, q, k): 
                        # Default mock behavior
                        return np.array([[1.5]], dtype=np.float32), np.array([[0]], dtype=np.int64)
                return MockIndex()
            def write_index(self, index, path): pass
            def read_index(self, path): return None
        
        self.faiss.faiss = MockFaissObj()
        self.faiss.index = self.faiss.faiss.IndexFlatL2(3072)
            
        self.bm25 = MockBM25()
        self.meta = MockMetadataStore()
        self.embedder = MockEmbedder()
        self.engine = QueryEngine(self.faiss, self.bm25, self.meta, self.embedder)

    def tearDown(self):
        if os.path.exists(self.tmp_meta):
            os.remove(self.tmp_meta)
        if os.path.exists(self.tmp_index):
            os.remove(self.tmp_index)

    def test_irrelevant_query_returns_nothing(self):
        # Index a dummy file
        self.faiss.add([[0.5]*3072], [{"path": "test1.txt", "text": "Some content"}])
        
        # Search for something that will have a high distance (mocked to 1.5)
        results = self.engine.search("irrelevant query")
        
        # High distance (1.5) should result in 0 results due to threshold
        self.assertEqual(len(results), 0)

    def test_metadata_mapping_is_unique(self):
        # Index two files, both have 1 chunk
        self.faiss.add([[0.1]*3072], [{"path": "file1.txt", "text": "content1"}])
        self.faiss.add([[0.2]*3072], [{"path": "file2.txt", "text": "content2"}])
        
        # Mock FAISS to return only the first index (0)
        import numpy as np
        self.faiss.index.search = lambda q, k: (np.array([[0.05]], dtype=np.float32), np.array([[0]], dtype=np.int64))
        
        results = self.engine.search("query")
        
        # Should only return file1.txt, NOT file2.txt
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].path, "file1.txt")

if __name__ == "__main__":
    unittest.main()
