import pandas as pd
import os
import csv


def run_etl():
    """Convert the AFCD workbook into the ingredient CSV."""
    excel_path = os.path.join(
        "src", "data", "cook", "AFCD Release 3 - Nutrient profiles.xlsx"
    )
    out_csv = os.path.join("src", "data", "cook", "ingredients.csv")
    print(f"Reading from {excel_path}...")
    df = pd.read_excel(
        excel_path, sheet_name="All solids & liquids per 100 g", skiprows=2
    )
    col_name = "Food Name"
    col_energy_kj = "Energy with dietary fibre, equated \n(kJ)"
    col_protein = "Protein \n(g)"
    col_carbs = "Available carbohydrate, without sugar alcohols \n(g)"
    col_fat = "Fat, total \n(g)"
    subset = df[[col_name, col_energy_kj, col_protein, col_carbs, col_fat]].copy()
    subset["ingredient"] = subset[col_name]
    subset["calories"] = (
        (pd.to_numeric(subset[col_energy_kj], errors="coerce") / 4.184)
        .round()
        .fillna(0)
        .astype(int)
    )
    subset["protein_g"] = (
        pd.to_numeric(subset[col_protein], errors="coerce").fillna(0).astype(int)
    )
    subset["carbs_g"] = (
        pd.to_numeric(subset[col_carbs], errors="coerce").fillna(0).astype(int)
    )
    subset["fat_g"] = (
        pd.to_numeric(subset[col_fat], errors="coerce").fillna(0).astype(int)
    )
    final_df = subset[["ingredient", "calories", "protein_g", "carbs_g", "fat_g"]]
    final_df = final_df.dropna(subset=["ingredient"])
    print(f"Writing {len(final_df)} ingredients to {out_csv}...")
    final_df.to_csv(
        out_csv, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC
    )
    print("ETL complete.")


if __name__ == "__main__":
    run_etl()
