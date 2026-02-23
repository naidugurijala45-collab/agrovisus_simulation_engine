from flask import Flask, request, jsonify
from PIL import Image
import torch
from torchvision import transforms
from model import CropDiseaseCNN  # Import your model definition
import os

app = Flask(__name__)

# Load the model
model = CropDiseaseCNN(num_classes=5)  # Adjust the num_classes according to your dataset
model.load_state_dict(torch.load('../models/best_model.pth', map_location=torch.device('cpu')))
model.eval()

# Define image preprocessing
transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

class_names = ["Healthy", "Rust", "Blight", "Spot", "Rot"]  # Update as per your dataset

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        image = Image.open(file).convert('RGB')
        image = transform(image).unsqueeze(0)

        with torch.no_grad():
            outputs = model(image)
            _, predicted = torch.max(outputs, 1)
            predicted_class = class_names[predicted.item()]

        return jsonify({'prediction': predicted_class})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
