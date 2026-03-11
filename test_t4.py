import sys
sys.path.insert(0, '.')
from trabajo4_sr_colaborativo import recomendar_usuario_usuario, recomendar_item_item, USERS_CF

u = USERS_CF[5]
print(f"Testing user {u}")

uu = recomendar_usuario_usuario(u)
if 'error' in uu:
    print("UU ERROR:", uu['error'])
else:
    recs = uu['recomendaciones']
    vecs = uu['vecinos']
    print(f"UU OK: {len(recs)} recs, {len(vecs)} vecinos")
    for r in recs[:3]:
        print(f"  {r['titulo'][:40]} pred={r['pred_rating']} sim={r['sim_avg']}")

ii = recomendar_item_item(u)
if 'error' in ii:
    print("II ERROR:", ii['error'])
else:
    recs2 = ii['recomendaciones']
    print(f"II OK: {len(recs2)} recs")
    for r in recs2[:3]:
        print(f"  {r['titulo'][:40]} pred={r['pred_rating']} sim={r['sim_avg']}")
