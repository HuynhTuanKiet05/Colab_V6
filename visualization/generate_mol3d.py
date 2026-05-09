"""
Generate 3D Molecular Structures from SMILES
=============================================
Converts SMILES strings from DrugInformation.csv to 3D SDF format
for ball-and-stick visualization with 3Dmol.js.
"""
import json
import os
import sys
import traceback

import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "AMDGT_original", "data", "C-dataset")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "public", "assets", "drug_mol3d.json")
DRUG_INFO_PATH = os.path.join(DATA_DIR, "DrugInformation.csv")


def smiles_to_sdf(smiles, max_attempts=3):
    """Convert SMILES to 3D SDF string with hydrogens."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None

        # Add hydrogens for realistic ball-and-stick display
        mol = Chem.AddHs(mol)

        # Generate 3D coordinates with ETKDG method
        params = AllChem.ETKDGv3()
        params.randomSeed = 42

        for attempt in range(max_attempts):
            result = AllChem.EmbedMolecule(mol, params)
            if result == 0:
                break
            params.randomSeed = 42 + attempt + 1
        else:
            # Fallback: try without distance geometry
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())

        # Optimize geometry
        try:
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
        except Exception:
            try:
                AllChem.UFFOptimizeMolecule(mol, maxIters=200)
            except Exception:
                pass

        # Convert to SDF string
        sdf = Chem.MolToMolBlock(mol)
        return sdf

    except Exception as e:
        return None


def get_atom_info(smiles):
    """Get atom counts by element for a molecule."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {}
        mol = Chem.AddHs(mol)
        atom_counts = {}
        for atom in mol.GetAtoms():
            symbol = atom.GetSymbol()
            atom_counts[symbol] = atom_counts.get(symbol, 0) + 1
        return atom_counts
    except Exception:
        return {}


def main():
    print("=" * 60)
    print("  3D Molecular Structure Generator (SMILES -> SDF)")
    print("=" * 60)

    # Load drug information
    print("[1/3] Loading drug information...")
    df = pd.read_csv(DRUG_INFO_PATH)
    df.columns = df.columns.str.strip()
    print(f"  Found {len(df)} drugs")

    # Generate 3D structures
    print("[2/3] Generating 3D molecular structures...")
    molecules = {}
    success = 0
    failed = 0

    for idx, row in df.iterrows():
        drug_id = str(row.get("id", f"DRUG_{idx}"))
        drug_name = str(row.get("name", f"Drug {idx}"))
        smiles = str(row.get("smiles", ""))

        if not smiles or smiles == "nan":
            failed += 1
            continue

        sdf = smiles_to_sdf(smiles)
        if sdf is None:
            failed += 1
            if failed <= 5:
                print(f"  [FAIL] {drug_name}: could not generate 3D")
            continue

        # Get molecular properties
        mol = Chem.MolFromSmiles(smiles)
        mol_weight = round(Descriptors.MolWt(mol), 1) if mol else 0
        formula = Chem.rdMolDescriptors.CalcMolFormula(mol) if mol else ""
        atom_info = get_atom_info(smiles)

        molecules[drug_id] = {
            "name": drug_name,
            "smiles": smiles[:200],
            "sdf": sdf,
            "mol_weight": mol_weight,
            "formula": formula,
            "atoms": atom_info,
            "heavy_atoms": mol.GetNumHeavyAtoms() if mol else 0,
        }
        success += 1

        if (idx + 1) % 50 == 0:
            print(f"  Progress: {idx + 1}/{len(df)} (success: {success}, failed: {failed})")

    print(f"  Completed: {success} success, {failed} failed out of {len(df)}")

    # Write output
    print("[3/3] Writing output...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    output = {
        "meta": {
            "total": success,
            "failed": failed,
            "source": "C-dataset DrugInformation.csv",
        },
        "molecules": molecules,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    file_size = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n[OK] Output: public/assets/drug_mol3d.json")
    print(f"   File size: {file_size:.2f} MB")
    print(f"   Total molecules: {success}")
    print("\n[DONE] Ready for 3Dmol.js rendering.")


if __name__ == "__main__":
    main()
