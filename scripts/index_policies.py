import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warrantymind.database import get_conn, seed_demo_data
from warrantymind.mcp_servers.policy_rag_mcp import _compute_dense_concept_vector

if __name__ == "__main__":
    seed_demo_data()
    conn = get_conn()
    rows = conn.execute("SELECT clause_id, title, program_type, text FROM policy_clauses").fetchall()
    conn.close()
    print(f"Indexed {len(rows)} policy clauses + relational dependency graph edges:")
    for r in rows:
        vec = _compute_dense_concept_vector(r["title"] + " " + r["text"])
        print(f"  - [{r['clause_id']}] ({r['program_type']}) {r['title']} | norm_vec={[round(v, 2) for v in vec]}")
