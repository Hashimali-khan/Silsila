import numpy as np
from app.services.privacy import privacy_service

def test_privacy_noise_enabled():
    # Enable
    privacy_service.enable()
    assert privacy_service.is_enabled is True
    
    vec = [1.0] * privacy_service.dim
    # With unit normalization, input length should be 1
    norm = np.linalg.norm(vec)
    vec = (np.array(vec) / norm).tolist()
    
    # Apply noise
    noised_vec = privacy_service.apply_noise(vec)
    
    # Check shape
    assert len(noised_vec) == privacy_service.dim
    
    # Check it changed (noise added)
    assert noised_vec != vec
    
    # Check it's unit length
    noised_norm = np.linalg.norm(noised_vec)
    assert np.isclose(noised_norm, 1.0)

def test_privacy_noise_disabled():
    privacy_service.disable()
    assert privacy_service.is_enabled is False
    
    vec = [1.0] * privacy_service.dim
    noised_vec = privacy_service.apply_noise(vec)
    
    # When disabled, should return exact same vector
    assert noised_vec == vec
    
    # Re-enable for other tests
    privacy_service.enable()
