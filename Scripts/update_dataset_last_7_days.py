import pandas as pd
import os
from datetime import datetime, timedelta

# Folder z lokalnymi plikami CSV
RAW_DATA_DIR = '../MlService/data/raw/'

# Ścieżka do datasetu
DATASET_PATH = '../MlService/data/dataset.csv'

# Kolumny bukmacherskie, które chcemy wyciągnąć
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

def fetch_recent_matches():
    today = datetime.now()
    week_ago = today - timedelta(days=7)

    all_recent = []

    # Przejdź po wszystkich plikach w ./data/raw/
    for filename in os.listdir(RAW_DATA_DIR):
        if filename.endswith('.csv'):
            filepath = os.path.join(RAW_DATA_DIR, filename)
            print(f"🔵 Reading {filename}...")

            try:
                df = pd.read_csv(filepath)

                if 'Date' not in df.columns:
                    print(f"⚠️ No 'Date' column in {filename}. Skipping...")
                    continue

                # Przetwórz daty
                df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Date'])

                # Wybierz mecze z ostatnich 7 dni
                mask = (df['Date'] >= week_ago) & (df['Date'] <= today)
                recent_matches = df.loc[mask]

                if not recent_matches.empty:
                    print(f"🟢 Found {len(recent_matches)} matches in {filename}")
                    recent_matches['league'] = filename.replace('.csv', '')
                    all_recent.append(recent_matches)
                else:
                    print(f"⚪ No recent matches in {filename}")

            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")

    if all_recent:
        return pd.concat(all_recent, ignore_index=True)
    else:
        return None

def process_and_append(matches):
    if matches is None or matches.empty:
        print("⚪ No new matches to process.")
        return

    print(f"🛠 Processing {len(matches)} matches...")

    matches = matches.dropna(subset=["FTR"])

    matches['home_win'] = matches['FTR'].apply(lambda x: 1 if x == 'H' else 0)

    features = BOOKMAKER_COLUMNS.copy()
    features.append('home_win')
    features.append('league')

    features = [col for col in features if col in matches.columns]

    new_data = matches[features].dropna()

    if os.path.exists(DATASET_PATH):
        dataset = pd.read_csv(DATASET_PATH)
        updated_dataset = pd.concat([dataset, new_data], ignore_index=True)

        # Usuń duplikaty — np. ten sam mecz znowu dodany
        updated_dataset = updated_dataset.drop_duplicates()

    else:
        updated_dataset = new_data

    os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
    updated_dataset.to_csv(DATASET_PATH, index=False)
    print(f"🟢 Dataset updated! Total rows now: {len(updated_dataset)}")

def main():
    recent_matches = fetch_recent_matches()
    process_and_append(recent_matches)

if __name__ == "__main__":
    main()
