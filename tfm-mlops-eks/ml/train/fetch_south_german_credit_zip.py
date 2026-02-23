import zipfile
import urllib.request
from pathlib import Path
import pandas as pd


def main() -> None:
    """
    Descarga el dataset South German Credit desde UCI (ZIP),
    extrae el archivo SouthGermanCredit.asc y lo convierte a CSV.

    - Guarda SIEMPRE en: <repo>/ml/train/data/
      (independiente del directorio desde donde ejecutes el script)
    - Limpia filas no numéricas (por ejemplo una cabecera embebida)
    - Deja el target 'kredit' con valores numéricos (0/1)
    """

    # 1) Carpeta destino: junto a este script -> ./data
    out_dir = Path(__file__).resolve().parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2) ZIP oficial del dataset en UCI (id=522)
    zip_url = "https://archive.ics.uci.edu/static/public/522/south%2Bgerman%2Bcredit.zip"
    zip_path = out_dir / "south_german_credit.zip"

    print("Downloading:", zip_url)
    urllib.request.urlretrieve(zip_url, zip_path)
    print("Saved zip:", zip_path)

    # 3) Extraer ZIP
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

    data_path = out_dir / "SouthGermanCredit.asc"
    if not data_path.exists():
        extracted = [p.name for p in out_dir.iterdir()]
        raise FileNotFoundError(
            f"No se encontró {data_path}. Archivos extraídos en {out_dir}: {extracted}"
        )

    # 4) Columnas según UCI: 20 features + target 'kredit' (21 columnas)
    cols = [
        "laufkont", "laufzeit", "moral", "verw", "hoehe",
        "sparkont", "beszeit", "rate", "famges", "buerge",
        "wohnzeit", "verm", "alter", "weitkred", "wohn",
        "bishkred", "beruf", "pers", "telef", "gastarb",
        "kredit"
    ]

    # 5) Leer .asc como texto para poder filtrar filas "sucias"
    #    El .asc viene separado por espacios (whitespace)
    df = pd.read_csv(data_path, sep=r"\s+", header=None, dtype=str)

    # 6) Limpiar: eliminar filas no numéricas (ej. cabecera embebida con 'kredit')
    #    Nos aseguramos de que la primera columna sea un número
    df = df[df[0].str.match(r"^\d+$", na=False)].copy()

    # 7) Validar número de columnas
    if df.shape[1] != len(cols):
        raise ValueError(
            f"Esperaba {len(cols)} columnas, pero llegaron {df.shape[1]}. "
            f"Revisa el archivo: {data_path}"
        )

    # 8) Aplicar nombres de columnas y convertir a int
    df.columns = cols
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="raise").astype(int)

    # 9) Guardar CSV final
    csv_path = out_dir / "south_german_credit.csv"
    df.to_csv(csv_path, index=False)

    print("CSV generado:", csv_path)
    print("Shape:", df.shape)
    print("Target unique values (kredit):", sorted(df["kredit"].unique()))
    print("Target distribution:\n", df["kredit"].value_counts().to_string())


if __name__ == "__main__":
    main()
