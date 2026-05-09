"""
Generate 3D Drug Chemical Space Data
=====================================
Reads mol2vec embeddings and drug information from C-dataset,
applies t-SNE to reduce 300D vectors to 3D, clusters with K-Means,
and computes molecular weight via RDKit. Outputs JSON for Plotly.js.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Try importing RDKit - fallback gracefully if not available
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
    print("[WARN] RDKit not found. Will use SMILES length as proxy for molecular weight.")

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "AMDGT_original", "data", "C-dataset")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "public", "assets", "drug_3d_data.json")

DRUG_INFO_PATH = os.path.join(DATA_DIR, "DrugInformation.csv")
MOL2VEC_PATH = os.path.join(DATA_DIR, "Drug_mol2vec.csv")

# ── Parameters ───────────────────────────────────────────────────────────
N_CLUSTERS = 8
TSNE_PERPLEXITY = 30
TSNE_LEARNING_RATE = 200
TSNE_N_ITER = 1000
RANDOM_STATE = 42


def load_data():
    """Load and merge drug information with mol2vec embeddings."""
    print("[1/5] Loading data...")

    # Load drug information (id, name, smiles)
    df_info = pd.read_csv(DRUG_INFO_PATH)
    df_info.columns = df_info.columns.str.strip()
    print(f"  Drug information: {len(df_info)} drugs")

    # Load mol2vec embeddings (index + 300 dims)
    df_mol2vec = pd.read_csv(MOL2VEC_PATH, header=None)
    print(f"  Mol2vec embeddings: {df_mol2vec.shape[0]} drugs x {df_mol2vec.shape[1] - 1} dims")

    # The first column in mol2vec is an index; the rest are features
    mol2vec_index = df_mol2vec.iloc[:, 0].values
    mol2vec_features = df_mol2vec.iloc[:, 1:].values

    # We align by position since both files are ordered the same
    n = min(len(df_info), len(mol2vec_features))
    df_info = df_info.iloc[:n].copy()
    mol2vec_features = mol2vec_features[:n]

    print(f"  Aligned: {n} drugs")
    return df_info, mol2vec_features


def compute_molecular_properties(df_info):
    """Compute molecular weight and atom count from SMILES."""
    print("[2/5] Computing molecular properties...")

    mol_weights = []
    atom_counts = []

    for _, row in df_info.iterrows():
        smiles = str(row.get("smiles", ""))
        if HAS_RDKIT and smiles:
            try:
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    mol_weights.append(Descriptors.MolWt(mol))
                    atom_counts.append(mol.GetNumHeavyAtoms())
                else:
                    mol_weights.append(len(smiles) * 5.0)
                    atom_counts.append(len(smiles) // 2)
            except Exception:
                mol_weights.append(len(smiles) * 5.0)
                atom_counts.append(len(smiles) // 2)
        else:
            # Fallback: use SMILES string length as proxy
            mol_weights.append(len(smiles) * 5.0)
            atom_counts.append(max(1, len(smiles) // 2))

    return np.array(mol_weights), np.array(atom_counts)


def apply_tsne(features):
    """Apply t-SNE to reduce 300D to 3D."""
    print("[3/5] Running t-SNE dimensionality reduction (300D -> 3D)...")
    print(f"  Perplexity: {TSNE_PERPLEXITY}, Iterations: {TSNE_N_ITER}")

    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    tsne = TSNE(
        n_components=3,
        perplexity=TSNE_PERPLEXITY,
        learning_rate=TSNE_LEARNING_RATE,
        max_iter=TSNE_N_ITER,
        random_state=RANDOM_STATE,
        init="pca",
    )
    coords_3d = tsne.fit_transform(features_scaled)

    print(f"  t-SNE complete. KL divergence: {tsne.kl_divergence_:.4f}")
    return coords_3d


def apply_clustering(coords_3d):
    """Apply K-Means clustering on the t-SNE 3D coordinates."""
    print(f"[4/5] Clustering drugs into {N_CLUSTERS} groups (K-Means on 3D coords)...")

    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(coords_3d)

    kmeans = KMeans(
        n_clusters=N_CLUSTERS,
        random_state=RANDOM_STATE,
        n_init=10,
    )
    clusters = kmeans.fit_predict(features_scaled)

    # Print cluster distribution
    unique, counts = np.unique(clusters, return_counts=True)
    for cls, cnt in zip(unique, counts):
        print(f"  Cluster {cls}: {cnt} drugs")

    return clusters


def build_json(df_info, coords_3d, clusters, mol_weights, atom_counts):
    """Build JSON output for Plotly.js."""
    print("[5/5] Building JSON output...")

    # Cluster color palette (vibrant, distinct colors)
    cluster_names = [
        "Peptides & Large Molecules",
        "Steroids & Hormones",
        "Heterocyclic Compounds",
        "Aromatic Amines",
        "Sulfonamides & Acids",
        "Alkaloids & Phenols",
        "Nucleosides & Sugars",
        "Small Molecules",
    ]

    drugs = []
    for i, row in df_info.iterrows():
        drugs.append({
            "id": str(row.get("id", f"DRUG_{i}")),
            "name": str(row.get("name", f"Drug {i}")),
            "smiles": str(row.get("smiles", ""))[:120],  # truncate very long SMILES
            "x": round(float(coords_3d[i, 0]), 4),
            "y": round(float(coords_3d[i, 1]), 4),
            "z": round(float(coords_3d[i, 2]), 4),
            "cluster": int(clusters[i]),
            "cluster_name": cluster_names[int(clusters[i]) % len(cluster_names)],
            "mol_weight": round(float(mol_weights[i]), 2),
            "atom_count": int(atom_counts[i]),
        })

    output = {
        "meta": {
            "total_drugs": len(drugs),
            "n_clusters": N_CLUSTERS,
            "method": "t-SNE (3D)",
            "perplexity": TSNE_PERPLEXITY,
            "rdkit_available": HAS_RDKIT,
        },
        "drugs": drugs,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=None)

    file_size = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n[OK] Output written to: public/assets/drug_3d_data.json")
    print(f"   File size: {file_size:.1f} KB")
    print(f"   Total drugs: {len(drugs)}")


def main():
    print("=" * 60)
    print("  Drug Chemical Space 3D Visualization - Data Generator")
    print("=" * 60)

    df_info, mol2vec_features = load_data()
    mol_weights, atom_counts = compute_molecular_properties(df_info)
    coords_3d = apply_tsne(mol2vec_features)
    clusters = apply_clustering(coords_3d)
    build_json(df_info, coords_3d, clusters, mol_weights, atom_counts)

    print("\n[DONE] Open index.php in browser to see the 3D chart.")


if __name__ == "__main__":
    main()
