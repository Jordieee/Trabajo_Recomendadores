from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import pandas as pd

# Importamos la lógica y datos pre-cargados del Trabajo 3
from trabajo3_sr_contenido import (
    recomendar_contenido, df_pref_norm, df_ratings_valid,
    pelicula_generos, df_peliculas, V_REF, USERS, id_dataset_to_name
)

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/users')
def get_users():
    """Devuelve la lista de usuarios disponibles."""
    # Convertimos los np.int64 a int estándar de Python para jsonify
    users_list = [int(u) for u in USERS]
    return jsonify(users_list)

@app.route('/api/recommend/<int:user_id>')
def recommend(user_id):
    """Devuelve las predicciones para un usuario en formato JSON."""
    if user_id not in USERS:
        return jsonify({"error": f"Usuario {user_id} no encontrado"}), 404
        
    df_top, pref = recomendar_contenido(
        user_id,
        df_pref_norm, df_ratings_valid,
        pelicula_generos, df_peliculas, V_REF,
        n_top_genres=5, umbral_salto=0.30,
        n_recomendaciones=10, verbose=False
    )
    
    if df_top.empty:
        return jsonify({"error": "No se encontraron recomendaciones"}), 404
        
    # Convertimos el DataFrame a lista de diccionarios
    recomendaciones = df_top.to_dict(orient='records')
    # Convertimos la Serie de preferencias a diccionario
    preferencias = {str(k): float(v) for k, v in pref.items()}
    
    return jsonify({
        "recomendaciones": recomendaciones,
        "preferencias": preferencias
    })

# Ruta adicional si queremos hacer proxy de carátulas o buscar info de película
# Por defecto lo haremos desde el frontend.

if __name__ == '__main__':
    # Usar threading para soportar múltiples conexiones simultáneas
    app.run(debug=True, port=5000, threaded=True)
