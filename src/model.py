import torch.nn as nn
from torchvision import models

class CropDiseaseCNN(nn.Module):
    def __init__(self, num_classes):
        super(CropDiseaseCNN, self).__init__()
        # Use ResNet18 with pretrained weights
        # Note: weights='DEFAULT' is the modern way, equivalent to pretrained=True
        try:
            from torchvision.models import ResNet18_Weights
            self.model = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        except ImportError:
            # Fallback for older torchvision versions
            self.model = models.resnet18(pretrained=True)
            
        # Replace the final fully connected layer
        num_ftrs = self.model.fc.in_features
        self.model.fc = nn.Linear(num_ftrs, num_classes)

    def forward(self, x):
        return self.model(x)
