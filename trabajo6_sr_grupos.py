"""
Trabajo 6: SR para Grupos
=========================
Implementa la recomendación para grupos de usuarios con múltiples técnicas de agregación:
  Consenso   : average, average_without_misery, multiplicative, additive_utilitarian
  Mayoría    : plurality_voting, approval_voting, borda_count
  Borderline : least_misery, most_pleasure, dictatorship

Pasos del proceso:
  1. Obtener recomendación individual para cada usuario del grupo.
  2. Eliminar ítems que estén en el histórico de CUALQUIER miembro del grupo.
  3. Agregar las listas individuales con la técnica seleccionada.
  4. Ordenar y devolver la lista recomendada al grupo.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any

# ── Importar módulos de trabajos anteriores ───────────────────────────────────
from trabajo3_sr_contenido import (
    recomendar_contenido, df_pref_norm, df_ratings_valid,
    pelicula_generos, df_peliculas, V_REF, USERS
)
from trabajo4_sr_colaborativo import recomendar_usuario_usuario, recomendar_item_item, USERS_CF
from trabajo5_sr_hibrido import recomendar_hibrido

# Máximo usuarios por grupo (decisión de diseño)
MAX_GROUP_SIZE = 10

# ── Módulo de histórico ───────────────────────────────────────────────────────

def get_user_history(user_id: int) -> set:
    """Devuelve el conjunto de movieIds que el usuario ya ha valorado."""
    mask = df_ratings_valid['userId'] == user_id
    return set(df_ratings_valid.loc[mask, 'movieId'].unique())


# ── Obtener recomendación individual ─────────────────────────────────────────

def get_individual_recs(user_id: int, algorithm: str, n: int = 10000) -> pd.DataFrame:
    """
    Obtiene la lista de recomendaciones individuales para un usuario.
    Devuelve un DataFrame con columnas: movieId, titulo, score (en [0, 1]).
    """
    if algorithm == 'contenido':
        res = recomendar_contenido(
            user_id, df_pref_norm, df_ratings_valid,
            pelicula_generos, df_peliculas, V_REF,
            n_top_genres=5, umbral_salto=0.30,
            n_recomendaciones=n, verbose=False
        )
        if isinstance(res, tuple):
            df, _ = res
        else:
            df = pd.DataFrame()
        if df.empty:
            return pd.DataFrame(columns=['movieId', 'titulo', 'score'])
        df = df[['movieId', 'titulo', 'score_final']].rename(columns={'score_final': 'score'})
        # score ya en [0, 1]
        return df.reset_index(drop=True)

    elif algorithm in ('collab-uu', 'collab-ii'):
        if algorithm == 'collab-uu':
            res = recomendar_usuario_usuario(user_id, k_vecinos=40, n_recomendaciones=n)
        else:
            res = recomendar_item_item(user_id, k_similares=40, n_recomendaciones=n)
        if 'error' in res:
            return pd.DataFrame(columns=['movieId', 'titulo', 'score'])
        df = pd.DataFrame(res['recomendaciones'])
        if df.empty:
            return pd.DataFrame(columns=['movieId', 'titulo', 'score'])
        df['score'] = df['pred_rating'] / 5.0  # normalizar a [0, 1]
        return df[['movieId', 'titulo', 'score']].reset_index(drop=True)

    elif algorithm == 'hibrido':
        res = recomendar_hibrido(user_id, n_recomendaciones=n)
        if 'error' in res:
            return pd.DataFrame(columns=['movieId', 'titulo', 'score'])
        df = pd.DataFrame(res['recomendaciones'])
        if df.empty:
            return pd.DataFrame(columns=['movieId', 'titulo', 'score'])
        df['score'] = df['score_hibrido']
        return df[['movieId', 'titulo', 'score']].reset_index(drop=True)

    return pd.DataFrame(columns=['movieId', 'titulo', 'score'])


# ── Construcción de la tabla ítem-usuario ────────────────────────────────────

def build_item_matrix(individual_recs: Dict[int, pd.DataFrame]) -> pd.DataFrame:
    """
    Construye un DataFrame donde cada fila es un ítem y cada columna es un usuario.
    Valores son los scores individuales (NaN si el usuario no tiene el ítem).
    """
    frames = []
    for uid, df in individual_recs.items():
        if df.empty:
            continue
        df = df.copy()
        df['userId'] = uid
        # Guardar también el rank dentro de la lista del usuario (para Borda)
        df['rank'] = df.index  # 0 = top
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Tabla pivote: rows=movieId, cols=userId, values=score
    pivot = combined.pivot_table(index=['movieId', 'titulo'], columns='userId', values='score', aggfunc='first')
    pivot.columns.name = None
    pivot = pivot.reset_index()

    # También añadir rank pivot
    rank_pivot = combined.pivot_table(index='movieId', columns='userId', values='rank', aggfunc='first')
    rank_pivot.columns = [f'rank_{c}' for c in rank_pivot.columns]
    rank_pivot = rank_pivot.reset_index()

    pivot = pivot.merge(rank_pivot, on='movieId', how='left')
    return pivot


# ── Técnicas de agregación ────────────────────────────────────────────────────

def aggregate_average(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """Media de los scores de todos los miembros."""
    scores = pivot[user_ids].values  # NaN para ítems no presentes
    return pd.Series(np.nanmean(scores, axis=1), index=pivot.index)


def aggregate_average_without_misery(pivot: pd.DataFrame, user_ids: List[int], threshold: float = 0.2) -> pd.Series:
    """Media solo de los scores que superan el umbral de miseria."""
    scores = pivot[user_ids].values.copy().astype(float)
    scores[scores < threshold] = np.nan
    result = np.nanmean(scores, axis=1)
    # Si todos están bajo el umbral, el resultado es NaN → tratar como 0
    result = np.nan_to_num(result, nan=0.0)
    return pd.Series(result, index=pivot.index)


def aggregate_multiplicative(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """Producto de los scores de todos los miembros (si falta, se usa 1 para no penalizar)."""
    scores = pivot[user_ids].values.copy().astype(float)
    # Los NaN se tratan como 0.5 (neutral) para no eliminar ítems que solo tiene uno
    scores = np.where(np.isnan(scores), 0.5, scores)
    result = np.prod(scores, axis=1)
    return pd.Series(result, index=pivot.index)


def aggregate_additive_utilitarian(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """Suma de los scores de todos los miembros (NaN=0)."""
    scores = pivot[user_ids].values.copy().astype(float)
    scores = np.nan_to_num(scores, nan=0.0)
    return pd.Series(scores.sum(axis=1), index=pivot.index)


def aggregate_least_misery(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """El score del grupo es el mínimo de los scores individuales."""
    scores = pivot[user_ids].values.astype(float)
    return pd.Series(np.nanmin(scores, axis=1), index=pivot.index)


def aggregate_most_pleasure(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """El score del grupo es el máximo de los scores individuales."""
    scores = pivot[user_ids].values.astype(float)
    return pd.Series(np.nanmax(scores, axis=1), index=pivot.index)


def aggregate_borda_count(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """
    Borda count: cada usuario vota sus ítems según su posición en la lista.
    El ítem en posición 0 recibe N-1 puntos, el de posición 1 recibe N-2, etc.
    El score final es la suma de los puntos Borda de todos los miembros.
    """
    n_items_total = len(pivot)
    borda_scores = np.zeros(len(pivot))

    for uid in user_ids:
        rank_col = f'rank_{uid}'
        if rank_col not in pivot.columns:
            continue
        ranks = pivot[rank_col].values.astype(float)
        # Normalizar: puntos = max_rank - rank (ítems no presentes tienen rank=NaN → 0 puntos)
        points = np.where(np.isnan(ranks), 0.0, (n_items_total - 1 - ranks))
        borda_scores += points

    # Normalizar a [0, 1]
    max_score = borda_scores.max()
    if max_score > 0:
        borda_scores = borda_scores / max_score
    return pd.Series(borda_scores, index=pivot.index)


def aggregate_plurality_voting(pivot: pd.DataFrame, user_ids: List[int]) -> pd.Series:
    """
    Plurality voting: cada usuario 'vota' su ítem más preferido.
    El score del ítem es el número de votos que recibe.
    """
    votes = np.zeros(len(pivot))
    for uid in user_ids:
        if uid not in pivot.columns:
            continue
        scores_u = pivot[uid].values.astype(float)
        best_idx = np.nanargmax(scores_u) if not np.all(np.isnan(scores_u)) else -1
        if best_idx >= 0:
            votes[best_idx] += 1

    # Normalizar
    max_v = votes.max()
    if max_v > 0:
        votes = votes / max_v
    return pd.Series(votes, index=pivot.index)


def aggregate_approval_voting(pivot: pd.DataFrame, user_ids: List[int], threshold: float = 0.5) -> pd.Series:
    """
    Approval voting: cada usuario 'aprueba' los ítems con score >= umbral.
    El score del ítem es la proporción de usuarios que lo aprueban.
    """
    scores = pivot[user_ids].values.astype(float)
    approved = (scores >= threshold).astype(float)
    approved = np.where(np.isnan(scores), 0.0, approved)
    result = approved.mean(axis=1)  # proporción de usuarios
    return pd.Series(result, index=pivot.index)


def aggregate_dictatorship(pivot: pd.DataFrame, user_ids: List[int], dictator_id: int = None) -> pd.Series:
    """
    Most Respected Person (Dictatorship): usa el score del dictador.
    Si no se especifica dictador, usa el usuario con más histórico (proxy de actividad).
    """
    if dictator_id is None or dictator_id not in user_ids:
        # Elegir el usuario con más ítems valorados como proxy de 'más respetado'
        max_history = -1
        for uid in user_ids:
            h = len(get_user_history(uid))
            if h > max_history:
                max_history = h
                dictator_id = uid

    if dictator_id not in pivot.columns:
        # Fallback: average
        return aggregate_average(pivot, user_ids)

    scores = pivot[dictator_id].values.astype(float)
    scores = np.nan_to_num(scores, nan=0.0)
    return pd.Series(scores, index=pivot.index)


AGGREGATION_FUNCTIONS = {
    'average': aggregate_average,
    'average_without_misery': aggregate_average_without_misery,
    'multiplicative': aggregate_multiplicative,
    'additive_utilitarian': aggregate_additive_utilitarian,
    'least_misery': aggregate_least_misery,
    'most_pleasure': aggregate_most_pleasure,
    'borda_count': aggregate_borda_count,
    'plurality_voting': aggregate_plurality_voting,
    'approval_voting': aggregate_approval_voting,
    'dictatorship': aggregate_dictatorship,
}


# ── Función principal ─────────────────────────────────────────────────────────

def recomendar_grupo(
    user_ids: List[int],
    algorithm: str = 'hibrido',
    aggregation: str = 'borda_count',
    n_recomendaciones: int = 10,
    dictator_id: int = None
) -> Dict[str, Any]:
    """
    Genera recomendaciones para un grupo de usuarios.

    Args:
        user_ids        : Lista de IDs de usuarios del grupo (máx. MAX_GROUP_SIZE).
        algorithm       : Técnica de recomendación individual
                          ('contenido', 'collab-uu', 'collab-ii', 'hibrido').
        aggregation     : Técnica de agregación de listas (ver AGGREGATION_FUNCTIONS).
        n_recomendaciones: Número de ítems a devolver.
        dictator_id     : ID del usuario "dictador" (solo para 'dictatorship').

    Returns:
        Diccionario con:
          - recomendaciones : Lista de dicts con la recomendación del grupo.
          - individual_recs  : Scores individuales de cada miembro para cada ítem recomendado.
          - users            : Lista de user_ids usados.
          - algorithm        : Técnica de recomendación individual.
          - aggregation      : Técnica de agregación.
    """
    # Validaciones
    if not user_ids:
        return {"error": "Se necesita al menos un usuario en el grupo."}
    if len(user_ids) > MAX_GROUP_SIZE:
        return {"error": f"El grupo no puede superar {MAX_GROUP_SIZE} usuarios."}
    if aggregation not in AGGREGATION_FUNCTIONS:
        return {"error": f"Técnica de agregación desconocida: {aggregation}"}

    # 1. Obtener recomendaciones individuales para cada usuario
    individual_recs: Dict[int, pd.DataFrame] = {}
    for uid in user_ids:
        recs = get_individual_recs(uid, algorithm, n=10000)
        individual_recs[uid] = recs

    # 2. Construir tabla ítem-usuario
    pivot = build_item_matrix(individual_recs)
    if pivot.empty:
        return {"error": "No se pudieron obtener recomendaciones para ningún miembro del grupo."}

    # Rellenar columnas de usuarios que no tengan entradas (pueden faltar si su lista está vacía)
    for uid in user_ids:
        if uid not in pivot.columns:
            pivot[uid] = np.nan

    # 3. Eliminar ítems del histórico de CUALQUIER miembro del grupo
    group_history = set()
    for uid in user_ids:
        group_history |= get_user_history(uid)

    pivot = pivot[~pivot['movieId'].isin(group_history)].reset_index(drop=True)
    if pivot.empty:
        return {"error": "Todos los ítems recomendados ya están en el histórico del grupo."}

    # 4. Calcular el score de grupo con la técnica de agregación
    agg_fn = AGGREGATION_FUNCTIONS[aggregation]
    if aggregation == 'dictatorship':
        group_scores = agg_fn(pivot, user_ids, dictator_id=dictator_id)
    else:
        group_scores = agg_fn(pivot, user_ids)

    pivot['group_score'] = group_scores.values

    # 5. Ordenar y seleccionar top-N
    pivot_sorted = pivot.sort_values('group_score', ascending=False).head(n_recomendaciones)

    # 6. Construir resultado
    # Calcular la "adecuación individual" de cada ítem para cada usuario del grupo
    result_recs = []
    for _, row in pivot_sorted.iterrows():
        item = {
            'movieId': int(row['movieId']),
            'titulo': row['titulo'],
            'group_score': round(float(row['group_score']), 4),
            'individual_scores': {}
        }
        # Scores por miembro (con estrellas)
        for uid in user_ids:
            s = row.get(uid, np.nan)
            item['individual_scores'][str(uid)] = round(float(s), 4) if not (isinstance(s, float) and np.isnan(s)) else None
        result_recs.append(item)

    return {
        "recomendaciones": result_recs,
        "users": user_ids,
        "algorithm": algorithm,
        "aggregation": aggregation,
        "dictator_id": dictator_id if aggregation == 'dictatorship' else None,
    }
