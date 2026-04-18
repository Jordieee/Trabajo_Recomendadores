"""
Módulo de Evaluación — Trabajo de Sistemas Recomendadores
==========================================================
Optimizado para pre-cálculo offline.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.model_selection import train_test_split

# Importar lógicas de recomendación
from trabajo3_sr_contenido import recomendar_contenido, df_pref_norm, df_ratings_valid, pelicula_generos, df_peliculas, V_REF
from trabajo4_sr_colaborativo import recomendar_usuario_usuario
from trabajo5_sr_hibrido import recomendar_hibrido

RESULT_DIR = Path('resultados')
RESULT_DIR.mkdir(exist_ok=True)

class Evaluator:
    def __init__(self, ratings_path='Data_set/ratings_small.csv'):
        self.df_ratings = pd.read_csv(ratings_path, sep=';', decimal=',')
        # Split 80/20 estratificado por usuario sería ideal, pero un simple split aleatorio es suficiente para este nivel
        self.train_df, self.test_df = train_test_split(self.df_ratings, test_size=0.2, random_state=42)
        
    def run_full_evaluation(self, n_users=100):
        """Calcula métricas globales para una muestra de usuarios y guarda en JSON."""
        print(f"🚀 Iniciando evaluación global (n={n_users} usuarios)...")
        results = {
            'contenido': self.evaluate_algo('contenido', n_users),
            'collab_uu': self.evaluate_algo('collab_uu', n_users),
            'hibrido': self.evaluate_algo('hibrido', n_users),
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        output_path = RESULT_DIR / 'global_metrics.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Evaluación completada. Resultados guardados en {output_path}")
        return results

    def evaluate_algo(self, algo_name, n_users):
        """Lógica genérica de evaluación para un algoritmo."""
        subset_users = self.test_df['userId'].unique()
        # Tomar una muestra representativa
        np.random.seed(42)
        if len(subset_users) > n_users:
            subset_users = np.random.choice(subset_users, n_users, replace=False)
            
        precisions = []
        errors = []
        n_hits = 0
        
        for uid in subset_users:
            # Usuarios que tienen datos en el set de test (lo que queremos predecir)
            actual_items = self.test_df[self.test_df['userId'] == uid]
            liked_items = set(actual_items[actual_items['rating'] >= 4.0]['movieId'])
            
            # Obtener películas vistas en entrenamiento (LAS QUE DEBEMOS EXCLUIR de la recomendación)
            vistas_train = set(self.train_df[self.train_df['userId'] == uid]['movieId'])
            
            # Obtener recomendaciones
            recs = []
            if algo_name == 'contenido':
                # Para contenido, pasamos el subset de training del dataframe de ratings
                train_ratings_subset = self.train_df[self.train_df['userId'] == uid]
                res = recomendar_contenido(uid, df_pref_norm, train_ratings_subset, pelicula_generos, df_peliculas, V_REF, n_recomendaciones=10, verbose=False)
                if isinstance(res, tuple): recs = res[0].to_dict('records')
            elif algo_name == 'collab_uu':
                res = recomendar_usuario_usuario(uid, n_recomendaciones=10, peliculas_vistas_override=vistas_train)
                if 'recomendaciones' in res: recs = res['recomendaciones']
            elif algo_name == 'hibrido':
                res = recomendar_hibrido(uid, n_recomendaciones=10, peliculas_vistas_override=vistas_train)
                if 'recomendaciones' in res: recs = res['recomendaciones']

            # Calcular Precision@10
            if liked_items:
                rec_ids = set(r['movieId'] for r in recs)
                hits = len(rec_ids & liked_items)
                precisions.append(hits / 10)
                n_hits += hits
                
            # Calcular MAE si hay predicciones disponibles
            if algo_name in ['collab_uu', 'hibrido']:
                preds_dict = {r['movieId']: r.get('pred_rating') or r.get('score_hibrido', 0)*5 for r in recs}
                for _, row in actual_items.iterrows():
                    mid = row['movieId']
                    if mid in preds_dict:
                        errors.append(abs(preds_dict[mid] - row['rating']))

        desc = {
            'contenido': 'Basado en atributos de películas (géneros). Buena precisión pero limitada por el historial del usuario.',
            'collab_uu': 'Basado en sabiduría social. El MAE indica qué tan cerca estamos del voto real del usuario.',
            'hibrido': 'Combina lo mejor de ambos mundos. Generalmente ofrece la mayor estabilidad y precisión.'
        }

        return {
            'precision': round(np.mean(precisions), 4) if precisions else 0.0,
            'mae': round(np.mean(errors), 4) if errors else 0.0,
            'desc': desc[algo_name]
        }

if __name__ == '__main__':
    ev = Evaluator()
    ev.run_full_evaluation(n_users=50) # Por defecto 50 para no tardar una eternidad en el script
