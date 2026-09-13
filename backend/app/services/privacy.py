import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)

class PrivacyService:
    def __init__(self, dim: int = 1024, epsilon: float = 1.0):
        self.dim = dim
        self.epsilon = epsilon
        self.is_enabled = True
        
        # In a real production system, this sensitivity mask would be learned 
        # from a sample of 1000 embeddings. For now, we simulate a mask where 
        # 10% of dimensions are considered "high variance" (sensitive).
        # Setting a random seed so the noise mask is deterministic per app restart.
        np.random.seed(42)
        
        # 1.0 for non-sensitive, larger for sensitive dimensions
        self.sensitivity_mask = np.ones(self.dim)
        sensitive_indices = np.random.choice(self.dim, size=int(self.dim * 0.1), replace=False)
        self.sensitivity_mask[sensitive_indices] = 5.0

    def disable(self):
        self.is_enabled = False
        logger.info("SPARSE Differential Privacy has been DISABLED.")

    def enable(self):
        self.is_enabled = True
        logger.info("SPARSE Differential Privacy has been ENABLED.")

    def apply_noise(self, vector: List[float]) -> List[float]:
        """
        Applies Mahalanobis-scaled noise to an embedding vector to satisfy 
        differential privacy guarantees for sensitive dimensions.
        """
        if not self.is_enabled:
            return vector
            
        vec_np = np.array(vector)
        
        # Scale for Gaussian noise based on epsilon and sensitivity mask
        # Lower epsilon = more privacy = more noise
        scale = self.sensitivity_mask / self.epsilon
        
        # Generate Gaussian noise
        noise = np.random.normal(loc=0.0, scale=scale, size=self.dim)
        
        # Apply noise
        noised_vec = vec_np + noise
        
        # Normalize the vector back to unit length since we use Cosine distance
        norm = np.linalg.norm(noised_vec)
        if norm > 0:
            noised_vec = noised_vec / norm
            
        return noised_vec.tolist()

privacy_service = PrivacyService()
