from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import pandas as pd
import os
import json

# Forzar backend no-GUI de matplotlib ANTES de importar T3 (que tiene plt.show())
import matplotlib
matplotlib.use('Agg')

# ── Trabajo 3: SR Basado en Contenido ────────────────────────────────────────
from trabajo3_sr_contenido import (
    recomendar_contenido, df_pref_norm, df_ratings_valid,
    pelicula_generos, df_peliculas, V_REF, USERS, id_dataset_to_name,
    df_generos
)

# ── Trabajo 4: SR Colaborativo ───────────────────────────────────────────────
from trabajo4_sr_colaborativo import (
    recomendar_usuario_usuario, recomendar_item_item, USERS_CF
)

# ── Trabajo 6: SR de Grupos ───────────────────────────────────────────────────
from trabajo6_sr_grupos import recomendar_grupo, AGGREGATION_FUNCTIONS

# ── Mejoras para el 10: Evaluación y Detalles ───────────────────────────────
from trabajo_evaluacion import Evaluator
import requests

app = Flask(__name__)
CORS(app)

# Configuración por defecto
TMDB_KEY_DEFAULT = "YOUR_TMDB_API_KEY" # Placeholder - reemplaza con una válida si tienes
BASE_TMDB_URL = "https://api.themoviedb.org/3"

# Unión de usuarios disponibles en ambos módulos
ALL_USERS = sorted(set([int(u) for u in USERS]) | set([int(u) for u in USERS_CF]))


@app.route('/')
def index():
    return render_template('index.html')


# ── Usuarios ─────────────────────────────────────────────────────────────────

@app.route('/api/users')
def get_users():
    """Devuelve la lista de usuarios disponibles (unión de T3 y T4)."""
    return jsonify(ALL_USERS)


@app.route('/api/generos')
def get_generos():
    """Devuelve la lista de géneros disponibles."""
    return jsonify(df_generos.to_dict(orient='records'))


# ── Contenido (Trabajo 3) ─────────────────────────────────────────────────────

@app.route('/api/recommend/<int:user_id>')
def recommend_contenido(user_id):
    """SR Basado en Contenido — Trabajo 3."""
    if user_id not in USERS:
        return jsonify({"error": f"Usuario {user_id} no disponible en SR Contenido"}), 404

    result = recomendar_contenido(
        user_id,
        df_pref_norm, df_ratings_valid,
        pelicula_generos, df_peliculas, V_REF,
        n_top_genres=5, umbral_salto=0.30,
        n_recomendaciones=10, verbose=False
    )

    if isinstance(result, tuple):
        df_top, pref = result
    else:
        df_top, pref = result, None

    if df_top.empty:
        return jsonify({"error": "No se encontraron recomendaciones"}), 404

    recomendaciones = df_top.to_dict(orient='records')
    preferencias = {str(k): float(v) for k, v in pref.items()} if pref is not None else {}

    return jsonify({
        "algoritmo": "contenido",
        "recomendaciones": recomendaciones,
        "preferencias": preferencias
    })


# ── Colaborativo Usuario-Usuario (Trabajo 4) ──────────────────────────────────

@app.route('/api/recommend/collab-uu/<int:user_id>')
def recommend_collab_uu(user_id):
    """SR Colaborativo Usuario-Usuario — Trabajo 4."""
    resultado = recomendar_usuario_usuario(user_id, k_vecinos=20, n_recomendaciones=10)

    if 'error' in resultado:
        return jsonify({"error": resultado['error']}), 404

    return jsonify({
        "algoritmo": "collab-uu",
        "recomendaciones": resultado['recomendaciones'],
        "vecinos": resultado.get('vecinos', [])
    })


# ── Colaborativo Ítem-Ítem (Trabajo 4) ───────────────────────────────────────

@app.route('/api/recommend/collab-ii/<int:user_id>')
def recommend_collab_ii(user_id):
    """SR Colaborativo Ítem-Ítem — Trabajo 4."""
    resultado = recomendar_item_item(user_id, k_similares=20, n_recomendaciones=10)

    if 'error' in resultado:
        return jsonify({"error": resultado['error']}), 404

    return jsonify({
        "algoritmo": "collab-ii",
        "recomendaciones": resultado['recomendaciones'],
    })


# ── Híbrido (Trabajo 5) ───────────────────────────────────────────────────────

@app.route('/api/recommend/hibrido/<int:user_id>')
def recommend_hibrido(user_id):
    """SR Híbrido Ponderado — Trabajo 5."""
    from trabajo5_sr_hibrido import recomendar_hibrido
    resultado = recomendar_hibrido(user_id, n_recomendaciones=10)
    
    if 'error' in resultado:
        return jsonify({"error": resultado['error']}), 404
        
    return jsonify({
        "algoritmo": "hibrido",
        "recomendaciones": resultado['recomendaciones'],
        "preferencias": resultado['preferencias'],
        "vecinos": resultado['vecinos'],
        "alpha": resultado.get('alpha', 0.5),
        "beta": resultado.get('beta', 0.5)
    })

# ── Grupos (Trabajo 6) ───────────────────────────────────────────────────────

@app.route('/api/recommend/grupo')
def recommend_grupo():
    """SR para Grupos — Trabajo 6."""
    # user_ids separados por comas, ej: ?user_ids=1,2,3
    raw_ids = request.args.get('user_ids', '')
    algorithm = request.args.get('algorithm', 'hibrido')
    aggregation = request.args.get('aggregation', 'borda_count')

    try:
        user_ids = [int(u.strip()) for u in raw_ids.split(',') if u.strip()]
    except ValueError:
        return jsonify({"error": "user_ids deben ser enteros separados por comas."}), 400

    if not user_ids:
        return jsonify({"error": "Se necesita al menos un user_id."}), 400

    dictator_id = request.args.get('dictator_id', None)
    if dictator_id is not None:
        try:
            dictator_id = int(dictator_id)
        except ValueError:
            dictator_id = None

    resultado = recomendar_grupo(
        user_ids=user_ids,
        algorithm=algorithm,
        aggregation=aggregation,
        n_recomendaciones=10,
        dictator_id=dictator_id
    )

    if 'error' in resultado:
        return jsonify({"error": resultado['error']}), 404

    return jsonify({
        "algoritmo": "grupo",
        **resultado
    })


@app.route('/api/aggregations')
def get_aggregations():
    """Devuelve la lista de técnicas de agregación disponibles."""
    return jsonify(list(AGGREGATION_FUNCTIONS.keys()))


# ── Mejoras: Evaluación (Métricas) ──────────────────────────────────────────

@app.route('/api/metrics')
def get_metrics():
    """Devuelve métricas pre-calculadas desde un archivo JSON."""
    metrics_path = os.path.join('resultados', 'global_metrics.json')
    if not os.path.exists(metrics_path):
        return jsonify({
            "error": "Métricas no disponibles", 
            "detail": "Ejecuta 'python precompute_metrics.py' para generarlas."
        }), 404
    
    with open(metrics_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)


# ── Mejoras: Usuario Nuevo (T3) ─────────────────────────────────────────────

@app.route('/api/recommend/new-user', methods=['POST'])
def recommend_new_user():
    """SR basado en contenido para un perfil de preferencias externo."""
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron preferencias"}), 400
    
    # Crear Series de pandas con las preferencias enviadas (0-10)
    # y normalizarlas a [0, 1]
    pref_series = pd.Series(data) / 10.0
    
    result = recomendar_contenido(
        None, # userId es None
        pref_series, # Pasamos la serie directamente como 'df_pref'
        df_ratings_valid,
        pelicula_generos, df_peliculas, V_REF,
        n_top_genres=5, umbral_salto=0.30,
        n_recomendaciones=10, verbose=False
    )

    if isinstance(result, tuple):
        df_top, _ = result
    else:
        df_top = pd.DataFrame()

    if df_top.empty:
        return jsonify({"error": "No se encontraron recomendaciones para este perfil"}), 404

    return jsonify({
        "algoritmo": "nuevo-usuario",
        "recomendaciones": df_top.to_dict(orient='records')
    })


# ── Mejoras: Detalles de Película ───────────────────────────────────────────

@app.route('/api/movie/<int:movie_id>')
def get_movie_details(movie_id):
    """Obtiene detalles enriquecidos (sinopsis, reparto) de TMDB."""
    api_key = request.args.get('api_key', TMDB_KEY_DEFAULT)
    
    # Intentar obtener el ID de TMDB (en nuestro dataset el id suele ser el de TMDB)
    # Si no, se puede buscar por título, pero probamos directo.
    
    url = f"{BASE_TMDB_URL}/movie/{movie_id}?api_key={api_key}&language=es-ES&append_to_response=credits"
    
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return jsonify({
                "overview": data.get("overview", "Sin sinopsis disponible."),
                "release_date": data.get("release_date", ""),
                "genres": [g["name"] for g in data.get("genres", [])],
                "cast": [c["name"] for c in data.get("credits", {}).get("cast", [])[:5]],
                "runtime": data.get("runtime", 0)
            })
        else:
            return jsonify({"error": "No se encontró información extra en TMDB"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
