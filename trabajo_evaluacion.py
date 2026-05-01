import pandas as pd
import numpy as np
import json
import math
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
        self.train_df, self.test_df = train_test_split(self.df_ratings, test_size=0.3, random_state=42)
        
    def run_full_evaluation(self, n_users=20):
        print(f"🚀 Iniciando evaluación global (n={n_users} usuarios)...")
        # Aseguramos seleccionar los mismos 20 usuarios para todas las técnicas
        subset_users = self.test_df['userId'].unique()
        np.random.seed(42)
        if len(subset_users) > n_users:
            subset_users = np.random.choice(subset_users, n_users, replace=False)

        metrics = {
            'contenido': {'precision': [], 'recall': [], 'f1': [], 'mae': [], 'ndcg': []},
            'collab_uu': {'precision': [], 'recall': [], 'f1': [], 'mae': [], 'ndcg': []},
            'hibrido': {'precision': [], 'recall': [], 'f1': [], 'mae': [], 'ndcg': []}
        }
        
        for uid in subset_users:
            # Lista de test para el usuario
            actual_items = self.test_df[self.test_df['userId'] == uid]
            
            # Relevantes de test: aquellos con ratio >= 3.5 (escala 0.5 a 5)
            relevant_test_items = actual_items[actual_items['rating'] >= 3.5]
            relevant_test_ids = set(relevant_test_items['movieId'])
            
            # Scores para nDCG: usamos el ratio del usuario como score de relevancia
            test_scores = {row['movieId']: row['rating'] for _, row in relevant_test_items.iterrows()}
            
            # Películas vistas en entrenamiento para excluirlas
            vistas_train = set(self.train_df[self.train_df['userId'] == uid]['movieId'])
            
            for algo_name in ['contenido', 'collab_uu', 'hibrido']:
                recs = []
                if algo_name == 'contenido':
                    train_ratings_subset = self.train_df[self.train_df['userId'] == uid]
                    res = recomendar_contenido(uid, df_pref_norm, train_ratings_subset, pelicula_generos, df_peliculas, V_REF, n_recomendaciones=10, verbose=False)
                    if isinstance(res, tuple): recs = res[0].to_dict('records')
                elif algo_name == 'collab_uu':
                    res = recomendar_usuario_usuario(uid, n_recomendaciones=10, peliculas_vistas_override=vistas_train)
                    if 'recomendaciones' in res: recs = res['recomendaciones']
                elif algo_name == 'hibrido':
                    res = recomendar_hibrido(uid, n_recomendaciones=10, peliculas_vistas_override=vistas_train)
                    if 'recomendaciones' in res: recs = res['recomendaciones']
                
                # Lista de recomendados
                rec_ids = [r['movieId'] for r in recs]
                rec_ids_set = set(rec_ids)
                
                # Intersección
                hits = len(rec_ids_set & relevant_test_ids)
                
                # Precisión, Recall, F1
                precision = hits / len(rec_ids) if len(rec_ids) > 0 else 0.0
                recall = hits / len(relevant_test_ids) if len(relevant_test_ids) > 0 else 0.0
                f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
                
                metrics[algo_name]['precision'].append(precision)
                metrics[algo_name]['recall'].append(recall)
                metrics[algo_name]['f1'].append(f1)
                
                # MAE: Intersección entre los recomendados y la lista real de test
                errors = []
                preds_dict = {}
                for r in recs:
                    if algo_name == 'contenido':
                        preds_dict[r['movieId']] = r.get('score_final', 0) * 5
                    elif algo_name == 'collab_uu':
                        preds_dict[r['movieId']] = r.get('pred_rating', 0)
                    elif algo_name == 'hibrido':
                        preds_dict[r['movieId']] = r.get('score_hibrido', 0) * 5
                        
                for _, row in actual_items.iterrows():
                    mid = row['movieId']
                    if mid in preds_dict:
                        errors.append(abs(preds_dict[mid] - row['rating']))
                        
                mae = np.mean(errors) if errors else np.nan
                metrics[algo_name]['mae'].append(mae)
                
                # nDCG
                dcg = 0.0
                for i, mid in enumerate(rec_ids):
                    score = test_scores.get(mid, 0.0)
                    dcg += score / math.log2((i + 1) + 1)
                    
                # Ideal DCG
                sorted_test_scores = sorted(test_scores.values(), reverse=True)
                idcg = 0.0
                for i, score in enumerate(sorted_test_scores):
                    idcg += score / math.log2((i + 1) + 1)
                    
                ndcg = dcg / idcg if idcg > 0 else 0.0
                metrics[algo_name]['ndcg'].append(ndcg)

        # Calcular promedios ignorando los NaNs en MAE
        averages = {}
        for algo in metrics:
            # Reemplazar NaN por 0 en la serie enviada al frontend para graficar (opcional, o dejarlo como null en JSON)
            # Para el promedio global sí usamos nanmean
            mae_array = np.array(metrics[algo]['mae'], dtype=float)
            avg_mae = np.nanmean(mae_array) if not np.all(np.isnan(mae_array)) else 0.0
            
            # Limpiar los NaN a 0.0 para el JSON (JSON no soporta NaN directamente)
            cleaned_mae_list = [0.0 if np.isnan(x) else x for x in metrics[algo]['mae']]
            metrics[algo]['mae'] = cleaned_mae_list
            
            averages[algo] = {
                'precision': np.mean(metrics[algo]['precision']),
                'recall': np.mean(metrics[algo]['recall']),
                'f1': np.mean(metrics[algo]['f1']),
                'mae': avg_mae,
                'ndcg': np.mean(metrics[algo]['ndcg']),
            }
            
        desc = {
            'contenido': 'Basado en atributos de películas (géneros).',
            'collab_uu': 'Basado en sabiduría social.',
            'hibrido': 'Combina lo mejor de ambos mundos.'
        }
        
        # Guardar resultados
        results = {
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'users': [int(x) for x in subset_users], # json serializable
            'per_user_metrics': metrics,
            'averages': averages
        }
        for algo in desc:
            results[algo] = {
                'precision': round(averages[algo]['precision'], 4),
                'recall': round(averages[algo]['recall'], 4),
                'f1': round(averages[algo]['f1'], 4),
                'mae': round(averages[algo]['mae'], 4),
                'ndcg': round(averages[algo]['ndcg'], 4),
                'desc': desc[algo]
            }

        output_path = RESULT_DIR / 'global_metrics.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Evaluación completada. Resultados guardados en {output_path}")
        return results

if __name__ == '__main__':
    ev = Evaluator()
    ev.run_full_evaluation(n_users=20)

