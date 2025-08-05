from flask import Flask, request, jsonify, render_template
import pickle
import base64
from io import BytesIO
from PIL import Image
import numpy as np

app = Flask(__name__)

# Load your trained recyclability model
with open('best_efficientnet_model.pth', 'rb') as f:
    model = pickle.load(f)

# Preprocess incoming image to model's expected input

def prepare_image(img: Image.Image) -> np.ndarray:
    img = img.convert('RGB')
    img = img.resize((224, 224))           # adjust to your model's input size
    arr = np.array(img) / 255.0            # scale to [0,1]
    arr = np.expand_dims(arr, axis=0)      # add batch dimension
    return arr

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.get_json() or {}
    img_data = data.get('image_data')
    if not img_data:
        return jsonify({'error': 'No image data provided.'}), 400

    # Remove base64 header
    _, encoded = img_data.split(',', 1)
    img_bytes = base64.b64decode(encoded)
    img = Image.open(BytesIO(img_bytes))

    # Predict
    input_arr = prepare_image(img)
    preds = model.predict(input_arr)

    # Confidence (if supported)
    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(input_arr)
        confidence = float(np.max(proba))
    else:
        confidence = 1.0

    # Label
    label = preds[0] if isinstance(preds, (list, np.ndarray)) else str(preds)

    return jsonify({'label': label, 'confidence': confidence})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
