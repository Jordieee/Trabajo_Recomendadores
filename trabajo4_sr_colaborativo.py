# =============================================================================
# TRABAJO 4 — SISTEMA DE RECOMENDACIÓN COLABORATIVO
# Máster MIARFID — Sistemas Recomendadores
# =============================================================================
# Implementa dos variantes de Filtrado Colaborativo:
#   A) Usuario-Usuario  (User-User CF)  — correlación de Pearson entre usuarios
#   B) Ítem-Ítem        (Item-Item CF)  — similitud de Pearson pre-computada
#
# La similitud ítem-ítem se pre-computa en startup para que las consultas
# sean inmediatas (~ms) en la API Flask.
# =============================================================================

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR   = Path('Data_set')
RESULT_DIR = Path('resultados')

# =============================================================================
# 1. CARGA DE DATOS
# =============================================================================
print("📦 [T4] Cargando datos para SR Colaborativo...")

df_ratings   = pd.read_csv(DATA_DIR / 'ratings_small.csv', sep=';', decimal=',')
df_peliculas = pd.read_csv(DATA_DIR / 'peliculas.csv',     sep=';', encoding='utf-8-sig', decimal=',')

id_to_titulo = dict(zip(df_peliculas['id'], df_peliculas['titulo']))
id_to_punt   = dict(zip(df_peliculas['id'], df_peliculas['puntuacion_media']))

# NUEVO: Cargar preferencias del T2/T3
df_pref_norm = pd.read_csv(RESULT_DIR / 'user_genre_matrix_normalized.csv', sep=';', decimal=',', index_col='userId')

# La profesora indica: rellenar con 0 (UNIÓN) si no hay suficientes datos para intersección pura
df_pref_union = df_pref_norm.fillna(0.0)

# =============================================================================
# 2. MATRIZ DE RATINGS  (usuarios × películas)
# =============================================================================
print("📊 [T4] Construyendo matriz usuarios × películas...")

# Asegurar que solo consideramos ratings de películas que realmente existan en nuestro catálogo
movies_in_peliculas = set(df_peliculas['id'].unique())
df_ratings_valid = df_ratings[df_ratings['movieId'].isin(movies_in_peliculas)]

rating_matrix: pd.DataFrame = df_ratings_valid.pivot_table(
    index='userId', columns='movieId', values='rating', aggfunc='mean'
)

# Películas con al menos 10 valoraciones (ítems populares)
valid_movies_mask = rating_matrix.notna().sum(axis=0) >= 10
rating_matrix     = rating_matrix.loc[:, valid_movies_mask]

# Usuarios con al menos 10 valoraciones
valid_users_mask = rating_matrix.notna().sum(axis=1) >= 10
rating_matrix    = rating_matrix.loc[valid_users_mask]

USERS_CF = sorted(rating_matrix.index.tolist())
print(f"✅ [T4] Matriz filtrada: {rating_matrix.shape}  |  Usuarios: {len(USERS_CF)}")

# Item matrix: películas × usuarios
item_matrix = rating_matrix.T   # shape: (n_movies, n_users)

# =============================================================================
# 3. PRE-COMPUTAR SIMILITUD ÍTEM-ÍTEM (Pearson, vectorizado)
# =============================================================================
# ESTO SE MANTIENE COMO EXTRA AUNQUE LA PROFESORA PIDA OBVIAR EL ITEM-ITEM
# =============================================================================
print("⚙️  [T4] Pre-computando similitudes ítem-ítem...")

# Convertir a numpy; NaN → 0 después de centrar
item_np = item_matrix.values.astype(float)      # (n_movies, n_users)

# Centrar cada ítem por su media (ignorando NaN)
item_means = np.nanmean(item_np, axis=1, keepdims=True)
item_centered = np.where(np.isnan(item_np), 0.0, item_np - item_means)

# Norma L2 por ítem
norms = np.linalg.norm(item_centered, axis=1, keepdims=True)
norms[norms == 0] = 1.0   # evitar división por cero

item_normed = item_centered / norms  # (n_movies, n_users)

# Similitud: (n_movies × n_movies)  Pearson = cosine sobre vectores centrados
item_sim_matrix = item_normed @ item_normed.T   # vectorizado
movie_ids = item_matrix.index.tolist()          # lista de movieId en orden

print(f"✅ [T4] Similitud ítem-ítem pre-computada: {item_sim_matrix.shape}")


def _get_item_sim(i: int, j: int) -> float:
    """Devuelve la similitud Pearson pre-computada entre ítem i e ítem j (índices de posición)."""
    return float(item_sim_matrix[i, j])


# Índice inverso movieId → posición en movie_ids
movie_id_to_pos = {mid: pos for pos, mid in enumerate(movie_ids)}

# =============================================================================
# 4. USER-USER COLLABORATIVE FILTERING
# =============================================================================

def recomendar_usuario_usuario(user_id: int,
                                k_vecinos: int = 40,
                                n_recomendaciones: int = 10,
                                sim_minima: float = 0.1,
                                min_rating_favorable: float = 3.0) -> dict:
    """
    Recomienda películas usando filtrado colaborativo Usuario-Usuario basado en PREFERENCIAS.
    
    1. Calcula la similitud de Pearson usando el vector COMPLETO de preferencias relleno con 0 (unión).
    2. Identifica los k_vecinos más similares (sim > 0). MAX 40-50 vecinos (clase).
    3. Selecciona ítems puntuados FAVORABLEMENTE por los vecinos (ej: >= 3.0).
    4. Calcula predicción: sum(sim(u,v) * r(v,i)) / sum(|sim(u,v)|) sin factores externos de ítem.
    """
    if user_id not in df_pref_union.index:
        return {'error': f'Usuario {user_id} no encontrado en matriz de preferencias.'}

    # Optimización: Computar Pearson vectorizado usando preferencias (unión)
    # FILTRAR: Solo usuarios que están en la matriz de ratings
    ratings_users = set(rating_matrix.index)
    df_pref_filtered = df_pref_union[df_pref_union.index.isin(ratings_users)]

    prefs_np = df_pref_filtered.values
    means = prefs_np.mean(axis=1, keepdims=True)
    centered = prefs_np - means
    norms = np.linalg.norm(centered, axis=1)
    
    try:
        u_idx = df_pref_filtered.index.get_loc(user_id)
    except KeyError:
        return {'error': f'Usuario {user_id} no tiene suficientes ratings para CF.'}
        
    u_centered = centered[u_idx]
    u_norm = norms[u_idx]
    
    similitudes = {}
    for i, other_id in enumerate(df_pref_filtered.index):
        if other_id == user_id: continue
        if norms[i] == 0 or u_norm == 0: continue
        
        sim = np.dot(u_centered, centered[i]) / (u_norm * norms[i])
        # Solo consideramos similitudes positivas grandes
        if not np.isnan(sim) and sim >= sim_minima:
            similitudes[other_id] = float(sim)
            
    if not similitudes:
        return {'error': 'No se encontraron vecinos con similitud suficiente en la matriz de ratings.'}

    # Vecinos con similitud más alta (k_vecinos = 40-50 como se indica en clase)
    top_vecinos = sorted(similitudes.items(), key=lambda x: x[1], reverse=True)[:k_vecinos]
    sim_dict = dict(top_vecinos)
    vecinos_ids = list(sim_dict.keys())

    # Historial del usuario
    u_ratings = rating_matrix.loc[user_id] if user_id in rating_matrix.index else pd.Series(dtype=float)
    peliculas_vistas = set(u_ratings.dropna().index)

    # Buscar ítems puntuados por los vecinos ("favorables")
    vecinos_ratings = rating_matrix.loc[vecinos_ids] if len(vecinos_ids) > 0 else pd.DataFrame()
    
    predicciones = []
    
    for movie_id in vecinos_ratings.columns:
        if movie_id in peliculas_vistas:
            continue
            
        ratings_for_movie = vecinos_ratings[movie_id].dropna()
        if ratings_for_movie.empty:
            continue
            
        # "seleccionar los ítems puntuados por los vecinos favorablemente"
        ratings_favorables = ratings_for_movie[ratings_for_movie >= min_rating_favorable]
        if ratings_favorables.empty:
            continue
            
        num = 0.0
        den = 0.0
        n_vecinos_val = 0
        
        for v_id, r_vi in ratings_favorables.items():
            if v_id in sim_dict:
                sim_v = sim_dict[v_id]
                num += sim_v * r_vi
                den += abs(sim_v)
                n_vecinos_val += 1
                
        if den > 0:
            pred_rating = max(0.5, min(5.0, num / den))
            
            # "No quiero puntuaciones medias que han dado a ese ítem" -> No se incluye externalidad
            predicciones.append({
                'movieId': int(movie_id),
                'titulo': id_to_titulo.get(movie_id, f'Película {movie_id}'),
                'pred_rating': round(pred_rating, 3),
                'sim_avg': round(den / n_vecinos_val, 3) if n_vecinos_val > 0 else 0,
                'n_vecinos': n_vecinos_val,
                'puntuacion': float(id_to_punt.get(movie_id, 0.0) or 0.0), # (Referencial UX, no para la fórmula)
            })

    if not predicciones:
        return {'error': 'No se pudieron calcular predicciones UU.'}

    predicciones.sort(key=lambda x: x['pred_rating'], reverse=True)

    return {
        'recomendaciones': predicciones[:n_recomendaciones],
        'vecinos': [{'userId': int(v), 'similitud': round(s, 3)} for v, s in top_vecinos[:10]],
    }


# =============================================================================
# 5. ITEM-ITEM COLLABORATIVE FILTERING  (usa similitudes pre-computadas)
# =============================================================================

def recomendar_item_item(user_id: int,
                          k_similares: int = 20,
                          n_recomendaciones: int = 10,
                          sim_minima: float = 0.1) -> dict:
    """
    Recomienda películas usando filtrado colaborativo Ítem-Ítem.
    Usa la matriz de similitud pre-computada en startup → consultas en ~ms.

    Fórmula: r̂(u,i) = μ_i + Σ sim(i,j)·(r_{u,j}−μ_j) / Σ|sim(i,j)|
    donde j ∈ {ítems ya valorados por u}.
    """
    if user_id not in rating_matrix.index:
        return {'error': f'Usuario {user_id} no encontrado o sin historial suficiente.'}

    u_ratings = rating_matrix.loc[user_id]

    # Películas vistas en el catálogo filtrado (películas con posición conocida)
    vistas_en_catálogo = {mid: float(u_ratings[mid]) for mid in u_ratings.index
                          if mid in movie_id_to_pos and not np.isnan(float(u_ratings[mid]))}

    if not vistas_en_catálogo:
        return {'error': 'El usuario no tiene películas vistas en el catálogo filtrado.'}

    candidatas = [mid for mid in movie_ids if mid not in vistas_en_catálogo]

    if not candidatas:
        return {'error': 'El usuario ha visto todas las películas del catálogo.'}

    predicciones = []

    for cand_id in candidatas:
        i_pos  = movie_id_to_pos[cand_id]
        i_mean = float(item_means[i_pos, 0])

        # Similitudes con ítems vistos (pre-computadas)
        sims = []
        for seen_id, r_u_j in vistas_en_catálogo.items():
            j_pos = movie_id_to_pos[seen_id]
            sim   = _get_item_sim(i_pos, j_pos)
            if sim >= sim_minima:
                j_mean = float(item_means[j_pos, 0])
                sims.append((seen_id, float(sim), float(r_u_j), j_mean))

        if not sims:
            continue

        sims.sort(key=lambda x: x[1], reverse=True)
        sims_top = sims[:k_similares]

        num = sum(sim * (r - jm) for _, sim, r, jm in sims_top)
        den = sum(abs(sim)        for _, sim, _, _  in sims_top)
        if den == 0:
            continue

        pred_rating = max(0.5, min(5.0, i_mean + num / den))
        sim_avg     = float(np.mean([s for _, s, _, _ in sims_top]))
        items_base  = [id_to_titulo.get(sid, str(sid)) for sid, _, _, _ in sims_top[:3]]

        predicciones.append({
            'movieId':     int(cand_id),
            'titulo':      id_to_titulo.get(cand_id, f'Película {cand_id}'),
            'pred_rating': round(pred_rating, 3),
            'sim_avg':     round(sim_avg, 3),
            'n_items':     len(sims_top),
            'items_base':  items_base,
            'puntuacion':  float(id_to_punt.get(cand_id, 0.0) or 0.0),
        })

    if not predicciones:
        return {'error': 'No se pudieron calcular predicciones II.'}

    predicciones.sort(key=lambda x: x['pred_rating'], reverse=True)
    return {'recomendaciones': predicciones[:n_recomendaciones]}


# =============================================================================
# 7. EJECUCIÓN STAND-ALONE (demo por consola)
# =============================================================================
if __name__ == '__main__':
    demo_user = USERS_CF[5]
    print(f"\n{'='*60}\nDEMO — Usuario {demo_user}\n{'='*60}")

    print("\n📡 User-User CF:")
    res_uu = recomendar_usuario_usuario(demo_user)
    if 'error' not in res_uu:
        print(f"  Vecinos: {len(res_uu['vecinos'])}")
        for i, r in enumerate(res_uu['recomendaciones'][:5], 1):
            print(f"  {i}. {r['titulo'][:45]:45} pred={r['pred_rating']:.2f}")
    else:
        print(f"  ERROR: {res_uu['error']}")

    print("\n🎬 Item-Item CF:")
    res_ii = recomendar_item_item(demo_user)
    if 'error' not in res_ii:
        for i, r in enumerate(res_ii['recomendaciones'][:5], 1):
            print(f"  {i}. {r['titulo'][:45]:45} pred={r['pred_rating']:.2f}")
    else:
        print(f"  ERROR: {res_ii['error']}")

    print("\n✅ Trabajo 4 completado.")
