import pandas as pd
import os

# Linki/kody plików CSV dla sezonu 24/25
LEAGUES = {
    "Premier League": "E0",
    "Serie A": "I1",
    "La Liga": "SP1",
    "Bundesliga": "D1",
    "Ligue 1": "F1",
    "Eredivisie": "N1",
    "Ekstraklasa": "PL1",
}

# Ścieżka folderu z lokalnie pobranymi plikami CSV
RAW_DATA_DIR = '../MlService/data/raw/'

# Ścieżka do zapisu datasetu
OUTPUT_CSV = '../MlService/data/dataset.csv'

# Kolumny bukmacherskie do wyciągnięcia
BOOKMAKER_COLUMNS = [
    "B365H", "B365D", "B365A",
    "BWH", "BWD", "BWA",
    "BFH", "BFD", "BFA",
    "PSH", "PSD", "PSA",
    "WHH", "WHD", "WHA",
    "1XBH", "1XBD", "1XBA",
    "MaxH", "MaxD", "MaxA",
    "AvgH", "AvgD", "AvgA",
    "B365>2.5", "B365<2.5",
    "P>2.5", "P<2.5",
    "Max>2.5", "Max<2.5",
    "Avg>2.5", "Avg<2.5",
    "AHh", "B365AHH", "B365AHA", "PAHH", "PAHA",
]

def load_league_data(code):
    filepath = os.path.join(RAW_DATA_DIR, f"{code}.csv")
    if not os.path.exists(filepath):
        print(f"⚠️ Warning: {filepath} not found.")
        return None

    df = pd.read_csv(filepath)
    return df

def prepare_dataset():
    print("🔵 Preparing dataset for 7 leagues (2024/25)...")

    all_matches = []

    for league_name, league_code in LEAGUES.items():
        print(f"🔵 Loading {league_name} ({league_code})...")

        df = load_league_data(league_code)

        if df is None:
            continue

        # Wyrzuć mecze bez wyniku
        df = df.dropna(subset=["FTR"])

        # Stwórz kolumnę home_win (target)
        df['home_win'] = df['FTR'].apply(lambda x: 1 if x == 'H' else 0)

        # Wybierz tylko interesujące kolumny
        features = BOOKMAKER_COLUMNS.copy()
        features.append('home_win')  # target też chcemy
        features = [col for col in features if col in df.columns]

        df_final = df[features]

        # Dodajemy ligę jako kolumnę (opcjonalnie, może pomóc modelowi)
        df_final['league'] = league_name

        all_matches.append(df_final)

    if not all_matches:
        print("❌ No leagues data found. Exiting.")
        return

    # Scal wszystko razem
    combined_df = pd.concat(all_matches, ignore_index=True)

    # Usuwanie wierszy z brakami
    combined_df = combined_df.dropna()

    print(f"✅ Final dataset rows: {len(combined_df)}")

    # Tworzymy folder jeśli nie istnieje
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    # Zapisujemy gotowy dataset
    combined_df.to_csv(OUTPUT_CSV, index=False)

    print(f"🟢 Dataset saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    prepare_dataset()
