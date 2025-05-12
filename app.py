import os
import zipfile
import tempfile
import replicate
import requests

from flask import Flask, render_template, request, send_file
from dotenv import load_dotenv

load_dotenv()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

REPLICATE_MODEL = "men1scus/birefnet"
REPLICATE_VERSION = "f74986db0355b58403ed20963af156525e2891ea3c2d499bfbfb2a28cd87c5d7"

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

    # Detectar si subieron un ZIP
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

    # Detectar si subieron archivos sueltos (1 o más)
    uploaded_files = request.files.getlist('images')
    for file in uploaded_files:
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            input_files.append(file_path)

    if not input_files:
        return "No se encontraron imágenes válidas para procesar.", 400

    # Procesar imágenes
    for image_path in input_files:
        with open(image_path, "rb") as img_file:
            try:
                print(f"Procesando imagen: {image_path}")
                prediction = client.run(
                    f"{REPLICATE_MODEL}:{REPLICATE_VERSION}",
                    input={"image": img_file}
                )
                if "output" not in prediction or not prediction["output"]:
                    print(f"Error: El modelo no devolvió una salida válida para la imagen {image_path}")
                    continue

                response = requests.get(prediction["output"])
                if response.status_code != 200:
                    print(f"Error al descargar la imagen procesada: {response.status_code}")
                    continue

                output_path = os.path.join(output_dir, os.path.basename(image_path))
                with open(output_path, "wb") as out_img:
                    out_img.write(response.content)
            except Exception as e:
                print(f"Error procesando {image_path}: {e}")

    # Validar si se generaron resultados
    if not os.listdir(output_dir):
        return "No se generaron resultados en el ZIP. Verifica las imágenes de entrada y el modelo de Replicate.", 500

    # Crear ZIP final
    result_zip = os.path.join(temp_dir, "result.zip")
    with zipfile.ZipFile(result_zip, 'w') as zipf:
        for f in os.listdir(output_dir):
            zipf.write(os.path.join(output_dir, f), arcname=f)

    print(f"Archivos generados en el ZIP: {os.listdir(output_dir)}")
    return send_file(result_zip, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)