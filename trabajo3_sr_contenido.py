# =============================================================================
# TRABAJO 3 — SISTEMA DE RECOMENDACIÓN BASADO EN CONTENIDO
# Máster MIARFID — Sistemas Recomendadores
# =============================================================================
# Construido sobre el Trabajo 2 (trabajo2_datos_base.ipynb), que ya genera:
#   - resultados/user_genre_matrix_raw.csv
#   - resultados/user_genre_matrix_normalized.csv
#   - resultados/user_genre_counts.csv
# =============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuración visual
plt.rcParams['figure.figsize'] = (14, 6)
plt.rcParams['font.size'] = 12
sns.set_style('whitegrid')
sns.set_palette('husl')

DATA_DIR    = Path('Data_set')
RESULT_DIR  = Path('resultados')

# =============================================================================
# %% ─── 1. CARGA DE DATOS ─────────────────────────────────────────────────────
# Cargamos tanto los CSVs generados en T2 como los datos originales necesarios.
# =============================================================================

print("\n" + "="*70)
print("📦 1. CARGA DE DATOS")
print("="*70)

# ── Datos originales ──────────────────────────────────────────────────────────
df_generos   = pd.read_csv(DATA_DIR / 'generos.csv',   sep=';', encoding='utf-8-sig')
df_peliculas = pd.read_csv(DATA_DIR / 'peliculas.csv', sep=';', encoding='utf-8-sig', decimal=',')
df_ratings   = pd.read_csv(DATA_DIR / 'ratings_small.csv', sep=';', decimal=',')

# ── Resultados del Trabajo 2 ──────────────────────────────────────────────────
df_pref_norm = pd.read_csv(RESULT_DIR / 'user_genre_matrix_normalized.csv', sep=';', decimal=',', index_col='userId')
df_pref_raw  = pd.read_csv(RESULT_DIR / 'user_genre_matrix_raw.csv',        sep=';', decimal=',', index_col='userId')

print(f"🎭 Géneros:   {len(df_generos)}")
print(f"🎬 Películas: {len(df_peliculas)}")
print(f"⭐ Ratings:   {len(df_ratings)}")
print(f"👤 Usuarios:  {len(df_pref_norm)}")
print(f"📊 Matriz preferencias: {df_pref_norm.shape}")

# ── Estructuras auxiliares (replicadas de T2) ─────────────────────────────────
genero_cols          = [col for col in df_peliculas.columns if col.startswith('id_genero')]
id_dataset_to_name   = dict(zip(df_generos['IdDataset'], df_generos['GeneroSP']))
genre_name_to_dataset_id = dict(zip(df_generos['GeneroSP'], df_generos['IdDataset']))

# Mapeo id_pelicula → lista de IdDataset de género
pelicula_generos: dict[int, list[int]] = {}
for _, row in df_peliculas.iterrows():
    mid = row['id']
    genres = []
    for col in genero_cols:
        val = row[col]
        if pd.notna(val) and val != '':
            try:
                genres.append(int(float(val)))
            except (ValueError, TypeError):
                pass
    pelicula_generos[mid] = genres

# Ratings válidos (películas con info de género)
movies_in_peliculas = set(df_peliculas['id'].unique())
df_ratings_valid    = df_ratings[df_ratings['movieId'].isin(movies_in_peliculas)].copy()

# Mediana de votos del catálogo (usada como referencia de fiabilidad)
V_REF = df_peliculas['votos'].median()
print(f"\n📌 Mediana de votos del catálogo (V_ref): {V_REF:.0f}")

# Lista de usuarios disponibles
USERS = sorted(df_pref_norm.index.tolist())

# =============================================================================
# %% ─── 2. RECAPITULACIÓN DEL TRABAJO 2 ──────────────────────────────────────
# =============================================================================

print("\n" + "="*70)
print("📋 2. RECAPITULACIÓN DEL TRABAJO 2")
print("="*70)
print("""
El Trabajo 2 construyó una MATRIZ DE PREFERENCIAS USUARIO-GÉNERO:
  • Para cada rating (u, i, r), se distribuyó r entre los k géneros de la película
    → contribución por género = r / k
  • Se calculó la media por género para cada usuario
  • Se normalizó por filas con Min-Max → valores en [0, 1]

Géneros no vistos por el usuario queden como NaN (no como 0).
Este trabajo 3 usa esa matriz como entrada para el SR basado en contenido.
""")

eg_user = USERS[3]
print(f"Ejemplo — perfil del usuario {eg_user}:")
print(df_pref_norm.loc[eg_user].dropna().sort_values(ascending=False).round(3).to_string())

# =============================================================================
# %% ─── 3. FILTRADO DEL VECTOR DE PREFERENCIAS ───────────────────────────────
# =============================================================================
# Objetivo: seleccionar los géneros más representativos del usuario, detectando
# si hay un "salto brusco" que indique que el resto de géneros no son relevantes.
# NO se modifica la matriz original; se trabaja sobre una copia filtrada.
# =============================================================================

print("\n" + "="*70)
print("🔍 3. FILTRADO DEL VECTOR DE PREFERENCIAS")
print("="*70)

def filtrar_preferencias(user_id: int,
                         df_pref: pd.DataFrame,
                         n_top: int = 5,
                         umbral_salto: float = 0.30) -> pd.Series:
    """
    Filtra el vector de preferencias normalizado de un usuario para quedarse
    con los géneros más representativos.

    Parámetros
    ----------
    user_id       : ID del usuario.
    df_pref       : DataFrame con la matriz normalizada [0,1] (↑ = más afinidad).
    n_top         : Máximo de géneros a seleccionar (por defecto 5).
    umbral_salto  : Caída relativa entre géneros consecutivos que indica que
                    los géneros inferiores no son relevantes. Por defecto 0.30
                    (30% de caída). Se aplica ANTES de alcanzar n_top si el salto
                    se produce antes.

    Retorna
    -------
    pd.Series con los géneros seleccionados y sus valores de preferencia.
    """
    if user_id is not None:
        if user_id not in df_pref.index:
            raise ValueError(f"Usuario {user_id} no encontrado en la matriz.")
        # Copiar y eliminar NaN (géneros no vistos → no se usan para recomendar)
        prefs = df_pref.loc[user_id].dropna().copy()
    elif df_pref is not None and isinstance(df_pref, pd.Series):
        prefs = df_pref.dropna().copy()
    else:
        raise ValueError("Se debe proporcionar user_id o un vector de preferencias pd.Series.")

    if len(prefs) == 0:
        return pd.Series(dtype=float)  # Usuario sin historial

    # Ordenar de mayor a menor preferencia
    prefs_sorted = prefs.sort_values(ascending=False)

    # Seleccionar hasta n_top, pero truncar antes si hay un salto brusco
    seleccionados = [prefs_sorted.index[0]]
    for i in range(1, min(n_top, len(prefs_sorted))):
        valor_actual  = prefs_sorted.iloc[i]
        valor_anterior = prefs_sorted.iloc[i - 1]

        # Detectar salto relativo (evitar división por cero)
        if valor_anterior > 0:
            caida_relativa = (valor_anterior - valor_actual) / valor_anterior
        else:
            caida_relativa = 0.0

        if caida_relativa > umbral_salto:
            # Salto brusco detectado: no incluir este ni los siguientes
            break

        seleccionados.append(prefs_sorted.index[i])

    return prefs_sorted.loc[seleccionados]


# ── Demo con un usuario ───────────────────────────────────────────────────────
print(f"\nFiltrado para usuario {eg_user}:")
pref_filtrada = filtrar_preferencias(eg_user, df_pref_norm, n_top=5, umbral_salto=0.30)
pref_completa = df_pref_norm.loc[eg_user].dropna().sort_values(ascending=False)

print(f"  Géneros con datos: {len(pref_completa)}")
print(f"  Géneros seleccionados tras filtrado: {len(pref_filtrada)}")
print(f"\n  Géneros TOP seleccionados:")
for g, v in pref_filtrada.items():
    print(f"    ★ {g:25s}: {v:.3f}")

# Gráfico: vector completo vs. vector filtrado
fig, ax = plt.subplots(figsize=(14, 5))
colors = ['#E74C3C' if g in pref_filtrada.index else '#AEB6BF' for g in pref_completa.index]
bars = ax.bar(range(len(pref_completa)), pref_completa.values, color=colors, edgecolor='white')
ax.set_xticks(range(len(pref_completa)))
ax.set_xticklabels(pref_completa.index, rotation=45, ha='right', fontsize=10)
ax.set_ylabel('Preferencia Normalizada [0,1]')
ax.set_title(f'Vector de preferencias — Usuario {eg_user}\n(rojo = géneros seleccionados, gris = descartados)', fontweight='bold')
ax.set_ylim(0, 1.1)
red_patch  = mpatches.Patch(color='#E74C3C', label=f'Seleccionados ({len(pref_filtrada)})')
grey_patch = mpatches.Patch(color='#AEB6BF', label='No seleccionados')
ax.legend(handles=[red_patch, grey_patch])
plt.tight_layout()
plt.savefig(RESULT_DIR / 'T3_fig1_vector_filtrado.png', dpi=150, bbox_inches='tight')
plt.show()
print(f"💾 Gráfico guardado: T3_fig1_vector_filtrado.png")

# =============================================================================
# %% ─── 4. FILTRADO DE ÍTEMS CANDIDATOS ──────────────────────────────────────
# =============================================================================
# Se seleccionan películas no vistas por el usuario que compartan al menos
# un género con el vector filtrado. Se excluye el historial del usuario.
# =============================================================================

print("\n" + "="*70)
print("🎬 4. FILTRADO DE ÍTEMS CANDIDATOS")
print("="*70)

def obtener_candidatas(user_id: int,
                       pref_filtrada: pd.Series,
                       df_ratings_v: pd.DataFrame,
                       pel_generos: dict) -> list[tuple]:
    """
    Obtiene la lista de películas candidatas para recomendar al usuario.

    Parámetros
    ----------
    user_id        : ID del usuario.
    pref_filtrada  : Serie con los géneros seleccionados (nombre → valor).
    df_ratings_v   : DataFrame de ratings válidos.
    pel_generos    : Diccionario {movieId: [IdDataset_genero, ...]}.

    Retorna
    -------
    Lista de (movieId, set_generos_coincidentes en IdDataset).
    """
    # Convertir nombres de géneros seleccionados a IdDataset
    top_ids = set()
    for nombre in pref_filtrada.index:
        did = genre_name_to_dataset_id.get(nombre)
        if did is not None:
            top_ids.add(did)

    # Historial del usuario
    peliculas_vistas = set(
        df_ratings_v.loc[df_ratings_v['userId'] == user_id, 'movieId'].values
    )

    candidatas = []
    for movie_id, generos in pel_generos.items():
        if movie_id in peliculas_vistas:
            continue
        coincidentes = set(generos) & top_ids
        if coincidentes:
            candidatas.append((movie_id, coincidentes))

    return candidatas


# ── Demo ──────────────────────────────────────────────────────────────────────
candidatas_demo = obtener_candidatas(
    eg_user, pref_filtrada, df_ratings_valid, pelicula_generos
)
print(f"\nUsuario {eg_user}:")
print(f"  Películas ya vistas: {df_ratings_valid[df_ratings_valid['userId']==eg_user]['movieId'].nunique()}")
print(f"  Películas candidatas encontradas: {len(candidatas_demo)}")
print(f"  Géneros de búsqueda: {list(pref_filtrada.index)}")

# =============================================================================
# %% ─── 5. CÁLCULO DEL SCORE DE INTERÉS r(u,i) ───────────────────────────────
# =============================================================================
#
# Fórmula propuesta:
#
#   r(u,i) = α · AfinidadGénero + β · CalidadPelícula + γ · Fiabilidad
#
# donde α + β + γ = 1.
#
# ┌─────────────────┬────────────────────────────────────────────────────────┐
# │ Componente      │ Cálculo                                                │
# ├─────────────────┼────────────────────────────────────────────────────────┤
# │ AfinidadGénero  │ Σ p(u,g) para g ∈ G_match  /  Σ p(u,g) para g ∈ G_top│
# │                 │ → qué proporción del interés del usuario cubre la peli.│
# ├─────────────────┼────────────────────────────────────────────────────────┤
# │ CalidadPelícula │ puntuación_media / 10  (normaliza a [0,1])             │
# │                 │ → calidad objetiva valorada por la comunidad.          │
# ├─────────────────┼────────────────────────────────────────────────────────┤
# │ Fiabilidad      │ min(1,  log(1+votos) / log(1+V_ref) )                  │
# │                 │ → confianza en la puntuación media (más votos = más    │
# │                 │   fiable); V_ref = mediana de votos del catálogo.      │
# └─────────────────┴────────────────────────────────────────────────────────┘
#
# Justificación de los pesos por defecto (α=0.50, β=0.30, γ=0.20):
#   • La afinidad personal es el factor dominante (50%) → personalización.
#   • La calidad objetiva pesa un 30% → no recomendar "basura" aunque guste.
#   • La fiabilidad pondera suavemente (20%) → penalizar películas oscuras
#     con 2 votos y media 9.9, pero no eliminarlas del todo.
# =============================================================================

print("\n" + "="*70)
print("📐 5. CÁLCULO DEL SCORE DE INTERÉS r(u,i)")
print("="*70)
print("""
  r(u,i) = α·AfinidadGénero + β·CalidadPelícula + γ·Fiabilidad
  
  con  α=0.50, β=0.30, γ=0.20  (configurables)
""")

def calcular_score(movie_id: int,
                   generos_coincidentes: set,
                   pref_filtrada: pd.Series,
                   df_pel: pd.DataFrame,
                   v_ref: float,
                   alpha: float = 0.50,
                   beta:  float = 0.30,
                   gamma: float = 0.20) -> dict:
    """
    Calcula el score de interés r(u,i) para un usuario y una película.

    Retorna un dict con el score final y los componentes individuales.
    """
    # ── Componente 1: Afinidad de género ─────────────────────────────────────
    # Convertir géneros coincidentes (IdDataset) a nombres
    nombres_coincidentes = [id_dataset_to_name[g] for g in generos_coincidentes
                            if g in id_dataset_to_name]
    # Solo los que están en el vector filtrado del usuario
    nombres_en_top = [n for n in nombres_coincidentes if n in pref_filtrada.index]

    suma_match = sum(pref_filtrada[n] for n in nombres_en_top) if nombres_en_top else 0.0
    suma_total = pref_filtrada.sum()
    afinidad   = suma_match / suma_total if suma_total > 0 else 0.0

    # ── Componente 2: Calidad de la película ──────────────────────────────────
    fila = df_pel[df_pel['id'] == movie_id]
    if fila.empty:
        return None

    puntuacion = float(fila['puntuacion_media'].values[0])
    votos      = float(fila['votos'].values[0]) if pd.notna(fila['votos'].values[0]) else 0.0
    titulo     = fila['titulo'].values[0]

    calidad = puntuacion / 10.0  # normalizado a [0,1]

    # ── Componente 3: Fiabilidad ──────────────────────────────────────────────
    if v_ref > 0 and votos > 0:
        fiabilidad = min(1.0, np.log1p(votos) / np.log1p(v_ref))
    else:
        fiabilidad = 0.0

    # ── Score final ───────────────────────────────────────────────────────────
    score = alpha * afinidad + beta * calidad + gamma * fiabilidad

    return {
        'movieId':       movie_id,
        'titulo':        titulo,
        'puntuacion':    puntuacion,
        'votos':         int(votos),
        'generos_match': ', '.join(nombres_en_top),
        'n_match':       len(nombres_en_top),
        'score_afinidad':  round(afinidad,   4),
        'score_calidad':   round(calidad,    4),
        'score_fiabilidad':round(fiabilidad, 4),
        'score_final':     round(score,      4),
    }


# ── Ejemplo manual de cálculo ─────────────────────────────────────────────────
print("Ejemplo manual de cálculo para 3 películas candidatas:")
muestra = candidatas_demo[:3]
for mid, coincidentes in muestra:
    res = calcular_score(mid, coincidentes, pref_filtrada, df_peliculas, V_REF)
    if res:
        print(f"\n  🎬 {res['titulo']} (id={mid})")
        print(f"     Géneros coincidentes : {res['generos_match']}")
        print(f"     Afinidad             : {res['score_afinidad']:.4f}  (×0.50 = {0.5*res['score_afinidad']:.4f})")
        print(f"     Calidad              : {res['score_calidad']:.4f}  (×0.30 = {0.3*res['score_calidad']:.4f})")
        print(f"     Fiabilidad           : {res['score_fiabilidad']:.4f}  (×0.20 = {0.2*res['score_fiabilidad']:.4f})")
        print(f"     SCORE FINAL          : {res['score_final']:.4f}")

# =============================================================================
# %% ─── 6. PIPELINE COMPLETO DE RECOMENDACIÓN ────────────────────────────────
# =============================================================================

print("\n" + "="*70)
print("🚀 6. PIPELINE COMPLETO DE RECOMENDACIÓN (TOP 10)")
print("="*70)

def recomendar_contenido(user_id: int,
                         df_pref: pd.DataFrame,
                         df_ratings_v: pd.DataFrame,
                         pel_generos: dict,
                         df_pel: pd.DataFrame,
                         v_ref: float,
                         n_top_genres: int = 5,
                         umbral_salto: float = 0.30,
                         n_recomendaciones: int = 10,
                         alpha: float = 0.50,
                         beta:  float = 0.30,
                         gamma: float = 0.20,
                         verbose: bool = True) -> pd.DataFrame:
    """
    Pipeline completo de recomendación basada en contenido.

    Pasos:
      1. Filtrar el vector de preferencias del usuario.
      2. Obtener películas candidatas (no vistas, géneros coincidentes).
      3. Calcular el score r(u,i) para cada candidata.
      4. Ordenar de mayor a menor y devolver el Top N.

    Retorna DataFrame con las películas recomendadas y desglose de scores.
    """
    if user_id is not None and user_id not in df_pref.index:
        print(f"⚠️ Usuario {user_id} sin datos de preferencia.")
        return pd.DataFrame()

    # PASO 1: Filtrado de preferencias
    pref = filtrar_preferencias(user_id, df_pref, n_top=n_top_genres, umbral_salto=umbral_salto)
    if len(pref) == 0:
        print(f"⚠️ Usuario {user_id} sin géneros en el vector filtrado.")
        return pd.DataFrame()

    if verbose:
        print(f"\n👤 Usuario {user_id}")
        print(f"   Géneros seleccionados ({len(pref)}): {', '.join(pref.index.tolist())}")

    # PASO 2: Filtrado de candidatas
    candidatas = obtener_candidatas(user_id, pref, df_ratings_v, pel_generos)
    if not candidatas:
        print(f"⚠️ No se encontraron candidatas para usuario {user_id}.")
        return pd.DataFrame()

    if verbose:
        print(f"   Candidatas encontradas: {len(candidatas)}")

    # PASO 3: Calcular score para cada candidata
    resultados = []
    for mid, coincidentes in candidatas:
        res = calcular_score(mid, coincidentes, pref, df_pel, v_ref, alpha, beta, gamma)
        if res is not None:
            resultados.append(res)

    if not resultados:
        print(f"⚠️ No se pudo calcular score para ninguna candidata.")
        return pd.DataFrame()

    # PASO 4: Ordenar y seleccionar Top N
    df_res = pd.DataFrame(resultados)
    df_top = df_res.nlargest(n_recomendaciones, 'score_final').reset_index(drop=True)
    df_top.index += 1  # ranking desde 1

    if verbose:
        print(f"\n🏆 TOP {n_recomendaciones} RECOMENDACIONES:")
        print(f"{'#':>3} {'Título':<45} {'Punt':>5} {'Votos':>6} {'Géneros':>30} {'Score':>7}")
        print("─" * 110)
        for rank, row in df_top.iterrows():
            titulo_trunc = row['titulo'][:43] + '..' if len(row['titulo']) > 45 else row['titulo']
            generos_trunc = row['generos_match'][:28] + '..' if len(row['generos_match']) > 30 else row['generos_match']
            print(f"{rank:>3}. {titulo_trunc:<45} {row['puntuacion']:>5.1f} {row['votos']:>6,} {generos_trunc:>30} {row['score_final']:>7.4f}")

    return df_top, pref


# ── Ejecutar para 4 usuarios representativos ─────────────────────────────────
if __name__ == '__main__':
    user_rating_counts = df_ratings_valid.groupby('userId').size().sort_values()
    example_users = [
        user_rating_counts.index[0],                          # Menos ratings
        user_rating_counts.index[len(user_rating_counts)//3],  # Tercil bajo
        user_rating_counts.index[2*len(user_rating_counts)//3],# Tercil alto
        user_rating_counts.index[-1]                           # Más ratings
    ]

    recomendaciones_por_usuario = {}
    perfiles_filtrados = {}

    for uid in example_users:
        print("\n" + "─"*70)
        result = recomendar_contenido(
            uid,
            df_pref_norm, df_ratings_valid,
            pelicula_generos, df_peliculas, V_REF,
            n_top_genres=5, umbral_salto=0.30,
            n_recomendaciones=10, verbose=True
        )
        if isinstance(result, tuple):
            recomendaciones_por_usuario[uid], perfiles_filtrados[uid] = result

    # =============================================================================
    # %% ─── 7. VISUALIZACIONES ───────────────────────────────────────────────────
    # =============================================================================

    print("\n" + "="*70)
    print("📊 7. VISUALIZACIONES")
    print("="*70)

    # ── 7.1 Desglose de scores para el usuario ejemplo ───────────────────────────
    if eg_user in recomendaciones_por_usuario:
        df_top_eg = recomendaciones_por_usuario[eg_user].head(10)

        fig, axes = plt.subplots(1, 2, figsize=(18, 7))

        # Barras apiladas de desglose
        titulos = [t[:35] + '…' if len(t) > 37 else t for t in df_top_eg['titulo']]
        x = range(len(df_top_eg))
        a_vals = df_top_eg['score_afinidad']   * 0.50
        b_vals = df_top_eg['score_calidad']    * 0.30
        g_vals = df_top_eg['score_fiabilidad'] * 0.20

        bars_a = axes[0].bar(x, a_vals, label='Afinidad (α=0.50)',   color='#E74C3C', edgecolor='white')
        bars_b = axes[0].bar(x, b_vals, bottom=a_vals, label='Calidad (β=0.30)', color='#3498DB', edgecolor='white')
        bars_g = axes[0].bar(x, g_vals, bottom=a_vals + b_vals, label='Fiabilidad (γ=0.20)', color='#2ECC71', edgecolor='white')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(titulos, rotation=45, ha='right', fontsize=9)
        axes[0].set_ylabel('Contribución al Score Final')
        axes[0].set_title(f'Desglose del Score — Usuario {eg_user}', fontweight='bold')
        axes[0].legend(loc='upper right')
        axes[0].set_ylim(0, 1)

        # Score final como barras horizontales
        df_top_sorted = df_top_eg.sort_values('score_final')
        titulos_h = [t[:40] + '…' if len(t) > 42 else t for t in df_top_sorted['titulo']]
        axes[1].barh(range(len(df_top_sorted)), df_top_sorted['score_final'], color='#6C5CE7', edgecolor='white', alpha=0.85)
        axes[1].set_yticks(range(len(df_top_sorted)))
        axes[1].set_yticklabels(titulos_h, fontsize=9)
        axes[1].set_xlabel('Score Final r(u,i)')
        axes[1].set_title(f'Top 10 — Score Final — Usuario {eg_user}', fontweight='bold')
        axes[1].set_xlim(0, 1)

        plt.tight_layout()
        plt.savefig(RESULT_DIR / 'T3_fig2_desglose_scores.png', dpi=150, bbox_inches='tight')
        plt.show()
        print("💾 Guardado: T3_fig2_desglose_scores.png")

    # ── 7.2 Radar chart — perfil completo vs. filtrado para 4 usuarios ───────────
    fig, axes = plt.subplots(2, 2, figsize=(18, 14), subplot_kw=dict(polar=True))
    axes = axes.flatten()
    genre_names_list = list(df_pref_norm.columns)
    N = len(genre_names_list)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles_plot = angles + angles[:1]

    for idx, uid in enumerate(example_users):
        if uid not in recomendaciones_por_usuario:
            continue
        ax = axes[idx]
        pref_full   = df_pref_norm.loc[uid].fillna(0).values
        pref_filt   = perfiles_filtrados[uid]
        n_ratings   = user_rating_counts[uid]

        values_full = np.concatenate([pref_full, [pref_full[0]]])
        ax.fill(angles_plot, values_full, alpha=0.15, color='#AEB6BF')
        ax.plot(angles_plot, values_full, linewidth=1.5, color='#AEB6BF', linestyle='--', label='Completo')

        # Resaltar géneros seleccionados
        pref_highlight = np.zeros(N)
        for i, gname in enumerate(genre_names_list):
            if gname in pref_filt.index:
                pref_highlight[i] = pref_full[i]
        values_hi = np.concatenate([pref_highlight, [pref_highlight[0]]])
        ax.fill(angles_plot, values_hi, alpha=0.45, color='#E74C3C')
        ax.plot(angles_plot, values_hi, linewidth=2, color='#E74C3C', label='Filtrado')

        ax.set_xticks(angles)
        ax.set_xticklabels(genre_names_list, size=8)
        ax.set_ylim(0, 1)
        ax.set_title(f'Usuario {uid} ({n_ratings} ratings)\n{", ".join(pref_filt.index.tolist())}',
                     fontweight='bold', size=11, pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)

    plt.suptitle('Perfil de Preferencias — Vector Completo vs. Filtrado', fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(RESULT_DIR / 'T3_fig3_radar_perfiles.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("💾 Guardado: T3_fig3_radar_perfiles.png")

    # ── 7.3 Comparativa T2 vs T3 para el usuario ejemplo ─────────────────────────
    print("\n" + "─"*70)
    print(f"📊 Comparativa T2 vs T3 — Usuario {eg_user}")
    print("─"*70)

    # Recomendador baseline del Trabajo 2 (recuperar lógica simplificada)
    def recomendar_t2_baseline(user_id, n_top=5, n_rec=10):
        """Recomendador simple del T2: top géneros + score_genero + puntuación_media."""
        prefs_norm = df_pref_norm.loc[user_id].dropna()
        top_genres = prefs_norm.nlargest(n_top)
        top_ids = set(genre_name_to_dataset_id[n] for n in top_genres.index if n in genre_name_to_dataset_id)
        vistas = set(df_ratings_valid[df_ratings_valid['userId']==user_id]['movieId'].values)

        candidatas = []
        for mid, generos in pelicula_generos.items():
            if mid in vistas: continue
            match = set(generos) & top_ids
            if match:
                candidatas.append((mid, len(match), len(match) / n_top))

        df_c = pd.DataFrame(candidatas, columns=['movieId', 'n_match', 'score_genero'])
        df_c = df_c.merge(df_peliculas[['id','titulo','puntuacion_media','votos']],
                          left_on='movieId', right_on='id', how='left')
        df_c = df_c[df_c['votos'] >= 50]
        max_p = df_c['puntuacion_media'].max() or 1
        df_c['score_final'] = 0.6 * df_c['score_genero'] + 0.4 * (df_c['puntuacion_media'] / max_p)
        return df_c.nlargest(n_rec, 'score_final')[['titulo', 'puntuacion_media', 'score_final']]

    df_t2 = recomendar_t2_baseline(eg_user)
    df_t3 = recomendaciones_por_usuario.get(eg_user, pd.DataFrame())

    print(f"\n{'TRABAJO 2':^35} | {'TRABAJO 3':^35}")
    print("─"*35 + "─┼─" + "─"*35)
    for i in range(10):
        t2_titulo = (df_t2.iloc[i]['titulo'][:32] + '…') if i < len(df_t2) and len(df_t2.iloc[i]['titulo']) > 35 else (df_t2.iloc[i]['titulo'] if i < len(df_t2) else '')
        t3_titulo = (df_t3.iloc[i]['titulo'][:32] + '…') if i < len(df_t3) and len(str(df_t3.iloc[i]['titulo'])) > 35 else (str(df_t3.iloc[i]['titulo']) if i < len(df_t3) else '')
        print(f"{i+1:2}. {t2_titulo:<32} | {i+1:2}. {t3_titulo}")

    # ── 7.4 Distribución del score_final sobre todas las candidatas ───────────────
    if eg_user in recomendaciones_por_usuario:
        pref_eg = perfiles_filtrados[eg_user]
        cands_eg = obtener_candidatas(eg_user, pref_eg, df_ratings_valid, pelicula_generos)
        all_scores = []
        for mid, coinc in cands_eg:
            res = calcular_score(mid, coinc, pref_eg, df_peliculas, V_REF)
            if res:
                all_scores.append(res['score_final'])

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.hist(all_scores, bins=50, color='#6C5CE7', edgecolor='white', alpha=0.85)
        top_scores = sorted(all_scores, reverse=True)[:10]
        ax.axvline(top_scores[-1], color='#E74C3C', linestyle='--', linewidth=2,
                   label=f'Umbral Top 10 ({top_scores[-1]:.4f})')
        ax.set_xlabel('Score Final r(u,i)')
        ax.set_ylabel('Nº de Películas Candidatas')
        ax.set_title(f'Distribución del Score de Interés — Usuario {eg_user}\n({len(all_scores)} candidatas)', fontweight='bold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(RESULT_DIR / 'T3_fig4_distribucion_scores.png', dpi=150, bbox_inches='tight')
        plt.show()
        print("💾 Guardado: T3_fig4_distribucion_scores.png")

    # =============================================================================
    # %% ─── 8. VALIDACIÓN MANUAL ─────────────────────────────────────────────────
    # =============================================================================
    # Verificamos que:
    #   a) Ninguna película recomendada está en el historial del usuario.
    #   b) Todos los géneros de las recomendadas coinciden con los del vector filtrado.
    #   c) El score se calcula correctamente para un caso conocido.
    # =============================================================================

    print("\n" + "="*70)
    print("✅ 8. VALIDACIÓN MANUAL")
    print("="*70)

    for uid in example_users:
        if uid not in recomendaciones_por_usuario:
            continue
        df_top_val = recomendaciones_por_usuario[uid]
        peliculas_vistas_val = set(df_ratings_valid[df_ratings_valid['userId']==uid]['movieId'].values)

        # a) Ninguna recomendada debe estar en historial
        recomendadas_ids = set(df_top_val['movieId'].values)
        solapamiento = recomendadas_ids & peliculas_vistas_val
        ok_a = "✅" if len(solapamiento) == 0 else f"❌ ({solapamiento})"

        # b) Todas deben tener al menos 1 género coincidente
        ok_b = "✅" if (df_top_val['n_match'] >= 1).all() else "❌"

        print(f"  Usuario {uid:>5}: sin solapamiento historial {ok_a} | géneros OK {ok_b}")

    # ── Verificación numérica manual para 1 película ──────────────────────────────
    print(f"\n🔢 Verificación numérica — Usuario {eg_user}:")
    mid_check, coinc_check = candidatas_demo[0]
    res_check = calcular_score(mid_check, coinc_check, pref_filtrada, df_peliculas, V_REF)
    if res_check:
        print(f"  Película: {res_check['titulo']} (id={mid_check})")
        print(f"  Género(s) coincidente(s): {res_check['generos_match']}")
        print(f"\n  Cálculo manual:")
        # Afinidad
        nombres_match = [id_dataset_to_name[g] for g in coinc_check if g in id_dataset_to_name]
        nombres_en_top = [n for n in nombres_match if n in pref_filtrada.index]
        suma_m = sum(pref_filtrada[n] for n in nombres_en_top)
        suma_t = pref_filtrada.sum()
        afinidad_m = suma_m / suma_t
        # Calidad
        fila = df_peliculas[df_peliculas['id']==mid_check]
        punt_m = float(fila['puntuacion_media'].values[0])
        vot_m  = float(fila['votos'].values[0])
        calidad_m    = punt_m / 10.0
        fiabilidad_m = min(1.0, np.log1p(vot_m) / np.log1p(V_REF))
        score_m      = 0.5 * afinidad_m + 0.3 * calidad_m + 0.2 * fiabilidad_m
        print(f"    Afinidad  = {suma_m:.4f}/{suma_t:.4f} = {afinidad_m:.4f}")
        print(f"    Calidad   = {punt_m:.1f}/10 = {calidad_m:.4f}")
        print(f"    Fiabilidad= log({vot_m:.0f}+1)/log({V_REF:.0f}+1) = {fiabilidad_m:.4f}")
        print(f"    Score     = 0.5×{afinidad_m:.4f} + 0.3×{calidad_m:.4f} + 0.2×{fiabilidad_m:.4f} = {score_m:.4f}")
        match = '✅ COINCIDE' if abs(score_m - res_check['score_final']) < 0.0001 else '❌ DISCREPANCIA'
        print(f"    Programa  = {res_check['score_final']:.4f}  →  {match}")

    # =============================================================================
    # %% ─── 9. CONCLUSIONES ───────────────────────────────────────────────────────
    # =============================================================================

    print("\n" + "="*70)
    print("📝 9. CONCLUSIONES")
    print("="*70)
    print(f"""
    TRABAJO 3 — SR Basado en Contenido

    Pipeline implementado:
      1. FILTRADO DE PREFERENCIAS
         • Se toman los top-5 géneros del usuario (vector normalizado del T2).
         • Se detecta salto brusco: si un género tiene ≥30% de caída relativa
           respecto al anterior, se trunca la selección ahí.
         • NO se modifica la matriz original del T2.

      2. FILTRADO DE CANDIDATAS
         • Se descartan películas ya valoradas por el usuario.
         • Solo pasan películas con ≥1 género coincidente con el vector filtrado.

      3. SCORE DE INTERÉS  r(u,i)
         r(u,i) = 0.50·AfinidadGénero + 0.30·CalidadPelícula + 0.20·Fiabilidad

         • AfinidadGénero : proporción de interés del usuario cubierta por la peli.
         • CalidadPelícula: puntuación_media normalizada a [0,1].
         • Fiabilidad     : confianza logarítmica según votos recibidos.

      4. RANKING
         • Las candidatas se ordenan de mayor a menor r(u,i).
         • Se presentan las Top 10.

    Ventajas respecto al recomendador del T2:
      ✓ La fórmula es 100% transparente y justificable para el usuario.
      ✓ El factor de fiabilidad evita películas con pocas valoraciones.
      ✓ El filtrado por salto evita incluir géneros marginales.
      ✓ Los pesos son configurables para ajustar el comportamiento.

    Posibles mejoras futuras:
      → Usar el vector RAW (no normalizado) para la afinidad, con escala [0,5].
      → Incorporar keywords/etiquetas para mayor granularidad.
      → Aplicar un umbral mínimo de votos configurable.
      → Combinar con filtrado colaborativo (enfoque híbrido).
    """)

    print("✅ Trabajo 3 completado.")
    print(f"💾 Figuras guardadas en: {RESULT_DIR.resolve()}")
