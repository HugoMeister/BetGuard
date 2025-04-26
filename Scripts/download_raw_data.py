import os
import requests

# Lista lig i ich linki do plików CSV na sezon 24/25
LEAGUES = {
    "E0": "https://www.football-data.co.uk/mmz4281/2425/E0.csv",   # Premier League
    "I1": "https://www.football-data.co.uk/mmz4281/2425/I1.csv",   # Serie A
    "SP1": "https://www.football-data.co.uk/mmz4281/2425/SP1.csv", # La Liga
    "D1": "https://www.football-data.co.uk/mmz4281/2425/D1.csv",   # Bundesliga
    "F1": "https://www.football-data.co.uk/mmz4281/2425/F1.csv",   # Ligue 1
    "N1": "https://www.football-data.co.uk/mmz4281/2425/N1.csv",   # Eredivisie
    "PL1": "https://www.football-data.co.uk/mmz4281/2425/PL1.csv", # Ekstraklasa
}

# Folder do zapisu plików
SAVE_DIR = '../MlService/data/raw/'

def download_file(url, save_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"🟢 Downloaded and saved: {save_path}")
    else:
        print(f"❌ Failed to download: {url}")

def download_all_leagues():
    os.makedirs(SAVE_DIR, exist_ok=True)

    for code, url in LEAGUES.items():
        save_path = os.path.join(SAVE_DIR, f"{code}.csv")
        print(f"🔵 Downloading {code}...")
        download_file(url, save_path)

    print("✅ All leagues downloaded!")

if __name__ == "__main__":
    download_all_leagues()
