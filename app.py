from flask import Flask, render_template, request, jsonify
from comparator import ImageComparator
import os

app = Flask(__name__)


# Route to serve the main HTML page
@app.route('/')
def index():
    return render_template('index.html')


# Route to handle the "Verify" button click (POST request)
@app.route('/verify', methods=['POST'])
def verify():
    try:
        # Check if both files were actually uploaded
        if 'figma' not in request.files or 'app' not in request.files:
            return jsonify({"error": "Please upload both images."}), 400

        figma_file = request.files['figma']
        app_file = request.files['app']

        if figma_file.filename == '' or app_file.filename == '':
            return jsonify({"error": "No file selected."}), 400

        # Call the Logic Layer (comparator.py)
        # We pass the file streams directly to keep it fast
        result = ImageComparator.compare(figma_file, app_file)

        # Return the JSON result to the frontend
        return jsonify(result)

    except Exception as e:
        print(f"Server Error: {str(e)}")
        return jsonify({"error": "Processing failed. Ensure files are valid images."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)