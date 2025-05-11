import os
import uuid
import zipfile
import shutil
import time
import base64
import requests
from flask import Flask, request, render_template, redirect, url_for

API_TOKEN = os.getenv("API_TOKEN")
MODEL_VERSION = os.getenv("MODEL_VERSION")

# URL del modelo en Replicate
PREDICT_URL = "https://api.replicate.com/v1/predictions"
HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json"
}

# Estructura de carpetas
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "resultados"
STATIC_FOLDER = "static"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_FOLDER)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        archivo_zip = request.files["archivo"]
        if archivo_zip.filename.endswith(".zip"):
            lote_id = str(uuid.uuid4())
            carpeta_lote = os.path.join(UPLOAD_FOLDER, lote_id)
            carpeta_resultado = os.path.join(RESULT_FOLDER, lote_id)
            os.makedirs(carpeta_lote, exist_ok=True)
            os.makedirs(carpeta_resultado, exist_ok=True)

            ruta_zip = os.path.join(carpeta_lote, "imagenes.zip")
            archivo_zip.save(ruta_zip)

            with zipfile.ZipFile(ruta_zip, 'r') as zip_ref:
                zip_ref.extractall(carpeta_lote)

            imagenes_procesadas = 0

            for nombre in os.listdir(carpeta_lote):
                ruta_imagen = os.path.join(carpeta_lote, nombre)
                if not nombre.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue

                with open(ruta_imagen, "rb") as file:
                    img_data = base64.b64encode(file.read()).decode("utf-8")

                response = requests.post(
                    PREDICT_URL,
                    headers=HEADERS,
                    json={
                        "version": MODEL_VERSION,
                        "input": {
                            "image": f"data:image/png;base64,{img_data}"
                        }
                    },
                )

                if response.status_code != 201:
                    print(f"❌ Error en: {nombre}")
                    continue

                pred_url = response.json()["urls"]["get"]

                while True:
                    result = requests.get(pred_url, headers=HEADERS).json()
                    if result["status"] == "succeeded":
                        output_url = result["output"]
                        break
                    elif result["status"] == "failed":
                        print(f"❌ Falló: {nombre}")
                        output_url = None
                        break
                    time.sleep(1)

                if output_url:
                    r = requests.get(output_url)
                    with open(os.path.join(carpeta_resultado, nombre), "wb") as out_file:
                        out_file.write(r.content)
                    imagenes_procesadas += 1

            # Crear archivo ZIP y archivo de info
            zip_final = os.path.join(RESULT_FOLDER, f"{lote_id}.zip")
            shutil.make_archive(zip_final.replace(".zip", ""), 'zip', carpeta_resultado)
            shutil.copy(zip_final, os.path.join(STATIC_FOLDER, f"{lote_id}.zip"))

            costo_total = imagenes_procesadas * 0.01
            with open(os.path.join(RESULT_FOLDER, f"{lote_id}_info.txt"), "w") as log_file:
                log_file.write(f"Imágenes procesadas: {imagenes_procesadas}\n")
                log_file.write(f"Costo total: ${costo_total:.2f}\n")

            return redirect(url_for("descargar", zip_id=lote_id))

    return render_template("index.html")


@app.route("/descargar/<zip_id>")
def descargar(zip_id):
    zip_path = os.path.join(STATIC_FOLDER, f"{zip_id}.zip")
    info_path = os.path.join(RESULT_FOLDER, f"{zip_id}_info.txt")

    if not os.path.exists(zip_path):
        return "Archivo no encontrado"

    with open(info_path, "r") as file:
        info = file.read().splitlines()
    
    cantidad = info[0].split(":")[1].strip()
    costo = info[1].split(":")[1].strip()

    return f"""
    <h2>✅ Lote procesado con éxito</h2>
    <p>Imágenes procesadas: <b>{cantidad}</b></p>
    <p>Total a pagar: <b>{costo}</b></p>
    <a href="/static/{zip_id}.zip" download>📥 Descargar imágenes</a>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
