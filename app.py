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

    # Detectar si subieron archivos sueltos
    uploaded_files = request.files.getlist('images')
    for file in uploaded_files:
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            input_files.append(file_path)

    if not input_files:
        print("No se encontraron imágenes válidas.")
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
                print("Predicción completa:", prediction)

                # Revisar si el resultado es válido
                output_url = prediction.get("output") if isinstance(prediction, dict) else prediction[0]
                if not output_url:
                    print(f"Error: No se encontró 'output' válido para {image_path}")
                    continue

                # Descargar imagen procesada
                response = requests.get(output_url)
                if response.status_code != 200:
                    print(f"Error al descargar desde {output_url}: código {response.status_code}")
                    continue

                # Guardar salida
                output_path = os.path.join(output_dir, os.path.basename(image_path))
                with open(output_path, "wb") as out_img:
                    out_img.write(response.content)
                print(f"Imagen procesada guardada en: {output_path}")
            except Exception as e:
                print(f"Error procesando {image_path}: {e}")

    # Validar si se generaron archivos
    output_files = os.listdir(output_dir)
    print("Archivos generados en output_dir:", output_files)
    if not output_files:
        return "No se generaron resultados. Verifica el modelo o las imágenes.", 500

    # Crear ZIP final
    result_zip = os.path.join(temp_dir, "result.zip")
    try:
        with zipfile.ZipFile(result_zip, 'w') as zipf:
            for f in output_files:
                zipf.write(os.path.join(output_dir, f), arcname=f)
        print(f"Archivo ZIP generado: {result_zip}")
    except Exception as e:
        print(f"Error al crear ZIP: {e}")
        return "Error al generar el archivo ZIP.", 500

    if not os.path.exists(result_zip):
        print("ZIP no existe en el sistema de archivos.")
        return "El archivo ZIP no fue generado.", 500

    return send_file(result_zip, as_attachment=True, mimetype='application/zip')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
