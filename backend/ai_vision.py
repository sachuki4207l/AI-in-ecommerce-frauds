"""
ai_vision.py — lightweight image comparison module using pretrained ResNet18.

Public function:
  compare_images(path_a: str, path_b: str) -> float

Returns a visual_mismatch_score in [0,1] where 0 -> identical and 1 -> very different.

The module loads ResNet18 once at import time and exposes a simple API for inference.
"""
from PIL import Image
import math
from typing import Optional

import torch
import torch.nn.functional as F
import torchvision.transforms as T
import torchvision.models as models

# Device selection (CPU-only by default; user may change if GPU available)
_DEVICE = torch.device("cpu")

# Load pretrained ResNet18 and use all layers except the final FC as a feature extractor.
_resnet = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
_feature_extractor = torch.nn.Sequential(*list(_resnet.children())[:-1])
_feature_extractor.eval()
_feature_extractor.to(_DEVICE)

# Preprocessing pipeline: load RGB, resize to 224x224, normalize with ImageNet stats
_preprocess = T.Compose([
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def _load_image(path: str) -> torch.Tensor:
    img = Image.open(path).convert("RGB")
    return _preprocess(img).unsqueeze(0).to(_DEVICE)


def _get_embedding(path: str) -> torch.Tensor:
    """Return a normalized 1-D embedding tensor (shape: [C])."""
    tensor = _load_image(path)
    with torch.no_grad():
        feat = _feature_extractor(tensor)  # shape [1, 512, 1, 1]
    feat = feat.flatten(start_dim=1)  # [1, 512]
    # L2 normalize
    feat = F.normalize(feat, p=2, dim=1)
    return feat.squeeze(0)  # [512]


def compare_images(path_a: str, path_b: str) -> float:
    """
    Compare two images and return a visual_mismatch_score in [0,1].

    Steps:
    - compute cosine similarity between L2-normalized embeddings
    - raw_mismatch = 1 - similarity
    - apply sigmoid((raw_mismatch - 0.5) * 8) to produce final confidence

    Any error (file missing, unreadable) returns 0.0 so the pipeline stays robust.
    """
    try:
        emb_a = _get_embedding(path_a)
        emb_b = _get_embedding(path_b)
    except Exception:
        return 0.0

    # cosine similarity in [-1,1]
    similarity = float(F.cosine_similarity(emb_a.unsqueeze(0), emb_b.unsqueeze(0), dim=1).item())
    # clamp similarity to [-1,1]
    similarity = max(-1.0, min(1.0, similarity))

    raw_mismatch = 1.0 - ((similarity + 1.0) / 2.0)  # map to [0,1] where 0 identical, 1 opposite
    raw_mismatch = max(0.0, min(1.0, raw_mismatch))

    # sigmoid scaling as requested
    confidence = 1.0 / (1.0 + math.exp(- (raw_mismatch - 0.5) * 8.0))
    # ensure in [0,1]
    confidence = max(0.0, min(1.0, confidence))
    return float(confidence)
