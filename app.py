from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import pandas as pd

# Forzar backend no-GUI de matplotlib ANTES de importar T3 (que tiene plt.show())
import matplotlib
matplotlib.use('Agg')

# ── Trabajo 3: SR Basado en Contenido ────────────────────────────────────────
from trabajo3_sr_contenido import (
    recomendar_contenido, df_pref_norm, df_ratings_valid,
    pelicula_generos, df_peliculas, V_REF, USERS, id_dataset_to_name
)

# ── Trabajo 4: SR Colaborativo (pre-carga la matriz al iniciar) ───────────────
from trabajo4_sr_colaborativo import (
    recomendar_usuario_usuario, recomendar_item_item, USERS_CF
)

app = Flask(__name__)
CORS(app)

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


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
