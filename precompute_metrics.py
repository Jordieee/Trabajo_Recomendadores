"""
Script de Pre-cómputo de Métricas — Trabajo 1-6
===============================================
Este script ejecuta la evaluación global de los modelos y guarda los resultados 
en un archivo JSON para que la aplicación web los cargue instantáneamente.
"""

from trabajo_evaluacion import Evaluator
import os

def main():
    print("--- INICIANDO PRE-CÓMPUTO DE MÉTRICAS ---")
    
    # Asegurar que estamos en el directorio correcto
    if not os.path.exists('Data_set/ratings_small.csv'):
        print("❌ Error: No se encuentra 'Data_set/ratings_small.csv'. Ejecuta el script desde la raíz del proyecto.")
        return

    # Instanciar evaluador
    evaluator = Evaluator()
    
    # Ejecutar evaluación (usamos 20 usuarios para una respuesta rápida)
    results = evaluator.run_full_evaluation(n_users=20)
    
    print("\nResumen de resultados:")
    for algo, res in results.items():
        if algo == 'timestamp': continue
        print(f"  • {algo.upper()}: Precision@10 = {res['precision']:.4f}, MAE = {res['mae']}")
        
    print("\n✨ Proceso finalizado. Ahora la aplicación cargará estas métricas al instante.")

if __name__ == '__main__':
    main()
