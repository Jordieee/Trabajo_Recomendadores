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
TMDB_KEY_DEFAULT = "f864d8898eea3f8c332fccc6faf0e61c"
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
    """SR para un perfil de preferencias externo (Usuario Nuevo)."""
    algorithm = request.args.get('algorithm', 'contenido')
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron preferencias"}), 400
    
    import pandas as pd
    import numpy as np
    from trabajo3_sr_contenido import obtener_candidatas, calcular_score, df_peliculas, V_REF, df_ratings_valid, pelicula_generos
    from trabajo4_sr_colaborativo import df_pref_union, rating_matrix
    
    pref_series_raw = pd.Series(data, dtype=float)
    
    if algorithm == 'contenido':
        pref_series = pref_series_raw * 10.0
        pref_series = pref_series[pref_series > 0].sort_values(ascending=False)
        if pref_series.empty:
            return jsonify({"error": "Debes valorar al menos un género por encima de 0."}), 400
            
        candidatas = obtener_candidatas(-1, pref_series, df_ratings_valid, pelicula_generos)
        resultados = []
        for mid, coincidentes in candidatas:
            res = calcular_score(mid, coincidentes, pref_series, df_peliculas, V_REF)
            if res is not None:
                resultados.append(res)
                
        if not resultados:
            return jsonify({"error": "No se encontraron recomendaciones."}), 404

        df_res = pd.DataFrame(resultados)
        df_top = df_res.nlargest(10, 'score_final').reset_index(drop=True)
        return jsonify({
            "algoritmo": "contenido",
            "recomendaciones": df_top.to_dict(orient='records'),
            "perfil_filtrado": {str(k): float(v) for k, v in pref_series.items()}
        })
        
    elif algorithm == 'collab-uu':
        pref_0_1 = pref_series_raw / 10.0
        user_vector = pd.Series(0.0, index=df_pref_union.columns)
        for g, v in pref_0_1.items():
            if g in user_vector.index:
                user_vector[g] = v
                
        u_centered = user_vector.values - user_vector.values.mean()
        u_norm = np.linalg.norm(u_centered)
        if u_norm == 0:
            return jsonify({"error": "Preferencias insuficientes para buscar vecinos."}), 400
            
        ratings_users = set(rating_matrix.index)
        df_pref_filtered = df_pref_union[df_pref_union.index.isin(ratings_users)]
        prefs_np = df_pref_filtered.values
        means = prefs_np.mean(axis=1, keepdims=True)
        centered = prefs_np - means
        norms = np.linalg.norm(centered, axis=1)
        
        similitudes = {}
        for i, other_id in enumerate(df_pref_filtered.index):
            if norms[i] == 0: continue
            sim = np.dot(u_centered, centered[i]) / (u_norm * norms[i])
            if not np.isnan(sim) and sim >= 0.1:
                similitudes[other_id] = float(sim)
                
        if not similitudes:
            return jsonify({"error": "No se encontraron vecinos similares."}), 404
            
        vecinos_top = dict(sorted(similitudes.items(), key=lambda item: item[1], reverse=True)[:40])
        predicciones = {}
        for vec_id, sim in vecinos_top.items():
            vec_ratings = rating_matrix.loc[vec_id].dropna()
            for movie_id, r in vec_ratings.items():
                if r < 3.0: continue
                if movie_id not in predicciones:
                    predicciones[movie_id] = {'sum_sim_r': 0, 'sum_sim': 0}
                predicciones[movie_id]['sum_sim_r'] += sim * r
                predicciones[movie_id]['sum_sim'] += sim
                
        resultados = []
        for mid, stats in predicciones.items():
            row = df_peliculas[df_peliculas['id'] == mid]
            if not row.empty:
                resultados.append({
                    'movieId': int(mid),
                    'titulo': row.iloc[0]['titulo'],
                    'pred_rating': round(stats['sum_sim_r'] / stats['sum_sim'], 4),
                    'sim_avg': round(stats['sum_sim'] / len(vecinos_top), 4)
                })
                
        df_res = pd.DataFrame(resultados)
        df_top = df_res.nlargest(10, 'pred_rating').reset_index(drop=True)
        return jsonify({
            "algoritmo": "collab-uu",
            "recomendaciones": df_top.to_dict(orient='records'),
            "vecinos": [{"userId": uid, "similitud": sim} for uid, sim in vecinos_top.items()]
        })
        
    elif algorithm == 'hibrido':
        # 1. Contenido
        pref_series_cont = pref_series_raw * 10.0
        pref_series_cont = pref_series_cont[pref_series_cont > 0].sort_values(ascending=False)
        res_cont = {}
        if not pref_series_cont.empty:
            candidatas = obtener_candidatas(-1, pref_series_cont, df_ratings_valid, pelicula_generos)
            for mid, coincidentes in candidatas:
                res = calcular_score(mid, coincidentes, pref_series_cont, df_peliculas, V_REF)
                if res is not None: res_cont[mid] = res['score_final']
                    
        # 2. Collab
        pref_0_1 = pref_series_raw / 10.0
        user_vector = pd.Series(0.0, index=df_pref_union.columns)
        for g, v in pref_0_1.items():
            if g in user_vector.index: user_vector[g] = v
        u_centered = user_vector.values - user_vector.values.mean()
        u_norm = np.linalg.norm(u_centered)
        res_col = {}
        vecinos_top = {}
        if u_norm > 0:
            ratings_users = set(rating_matrix.index)
            df_pref_filtered = df_pref_union[df_pref_union.index.isin(ratings_users)]
            prefs_np = df_pref_filtered.values
            means = prefs_np.mean(axis=1, keepdims=True)
            centered = prefs_np - means
            norms = np.linalg.norm(centered, axis=1)
            similitudes = {}
            for i, other_id in enumerate(df_pref_filtered.index):
                if norms[i] == 0: continue
                sim = np.dot(u_centered, centered[i]) / (u_norm * norms[i])
                if not np.isnan(sim) and sim >= 0.1: similitudes[other_id] = float(sim)
            vecinos_top = dict(sorted(similitudes.items(), key=lambda item: item[1], reverse=True)[:40])
            predicciones = {}
            for vec_id, sim in vecinos_top.items():
                vec_ratings = rating_matrix.loc[vec_id].dropna()
                for movie_id, r in vec_ratings.items():
                    if r < 3.0: continue
                    if movie_id not in predicciones: predicciones[movie_id] = {'sum_sim_r': 0, 'sum_sim': 0}
                    predicciones[movie_id]['sum_sim_r'] += sim * r
                    predicciones[movie_id]['sum_sim'] += sim
            for mid, stats in predicciones.items():
                res_col[mid] = stats['sum_sim_r'] / stats['sum_sim']

        todas_movies = set(res_cont.keys()).union(set(res_col.keys()))
        resultados = []
        for mid in todas_movies:
            sc_cont = res_cont.get(mid, 0.0)
            sc_col = res_col.get(mid, 0.0)
            sc_col_norm = sc_col / 5.0
            if sc_cont == 0: sc_col_norm *= 0.8
            if sc_col == 0: sc_cont *= 0.8
            final = 0.5 * sc_cont + 0.5 * sc_col_norm
            row = df_peliculas[df_peliculas['id'] == mid]
            if not row.empty:
                resultados.append({
                    'movieId': int(mid),
                    'titulo': row.iloc[0]['titulo'],
                    'score_hibrido': round(final, 4)
                })
                
        df_res = pd.DataFrame(resultados)
        if df_res.empty:
             return jsonify({"error": "No se encontraron recomendaciones."}), 404
             
        df_top = df_res.nlargest(10, 'score_hibrido').reset_index(drop=True)
        return jsonify({
            "algoritmo": "hibrido",
            "recomendaciones": df_top.to_dict(orient='records'),
            "vecinos": [{"userId": uid, "similitud": sim} for uid, sim in vecinos_top.items()]
        })


# ── Mejoras: Detalles y Pósters de Película ────────────────────────────────

@app.route('/api/poster/<int:movie_id>')
def get_poster(movie_id):
    """Devuelve la carátula de la película si existe localmente."""
    import glob, os
    from flask import send_file
    from trabajo3_sr_contenido import df_peliculas
    
    row = df_peliculas[df_peliculas['id'] == movie_id]
    if row.empty:
        return jsonify({"error": "Pelicula no encontrada"}), 404
        
    imdb_str = str(row.iloc[0]['imdb_id']) # e.g. "tt0113101" o "113101"
    # Extraer solo la parte numérica (quitando el 'tt' y los ceros a la izquierda que maneja int())
    try:
        imdb_numeric = int(''.join(filter(str.isdigit, imdb_str)))
    except ValueError:
        return jsonify({"error": "IMDB ID inválido"}), 400

    # Buscar cualquier archivo que termine en _{imdb_numeric}.jpg
    # en la carpeta Data_set/Car_tulas/archive/poster_downloads
    pattern = os.path.join("Data_set", "Car_tulas", "archive", "poster_downloads", f"*_{imdb_numeric}.jpg")
    matches = glob.glob(pattern)
    
    if matches:
        return send_file(matches[0], mimetype='image/jpeg')
    else:
        return jsonify({"error": "Póster no encontrado"}), 404


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
