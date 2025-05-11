import os
import zipfile
import tempfile
import replicate
import requests
import time

from flask import Flask, render_template, request, send_file
from dotenv import load_dotenv

load_dotenv()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

REPLICATE_MODEL = "men1scus/birefnet"
REPLICATE_VERSION = "acdf9c6b04b0ce7f8bbda7745f841b325530160a3fe2f58eecf229f78c8107e1"

client = replicate.Client(api_token=REPLICATE_API_TOKEN)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    input_files = []

    # Archivos .zip
    zip_file = request.files.get('zipfile')
    if zip_file and zip_file.filename.endswith('.zip'):
        zip_path = os.path.join(temp_dir, "upload.zip")
        zip_file.save(zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        input_files += [
            os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]

    # Archivos individuales
    uploaded_files = request.files.getlist('images')
    for file in uploaded_files:
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            input_files.append(file_path)

    if not input_files:
        return "No se encontraron imágenes válidas para procesar.", 400

    # Procesamiento con espera
    for image_path in input_files:
        try:
            with open(image_path, "rb") as img_file:
                prediction = client.predictions.create(
                    version=REPLICATE_VERSION,
                    input={"image": img_file}
                )

            # Espera activa a que termine el modelo
            while prediction.status not in ["succeeded", "failed", "canceled"]:
                time.sleep(1)
                prediction.reload()

            if prediction.status == "succeeded" and prediction.output:
                output_url = prediction.output
                response = requests.get(output_url)
                if response.status_code == 200:
                    filename = os.path.basename(image_path)
                    output_path = os.path.join(output_dir, filename)
                    with open(output_path, "wb") as out_file:
                        out_file.write(response.content)
                else:
                    print(f"❌ Falló la descarga de {output_url}")
            else:
                print(f"❌ Falló el procesamiento de {image_path}: {prediction.status}")

        except Exception as e:
            print(f"⚠️ Error con {image_path}: {e}")

    # Crear el ZIP
    result_zip = os.path.join(temp_dir, "result.zip")
    with zipfile.ZipFile(result_zip, 'w') as zipf:
        for f in os.listdir(output_dir):
            zipf.write(os.path.join(output_dir, f), arcname=f)

    return send_file(result_zip, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
