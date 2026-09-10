import os
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime

# Unsere Ziel-URL (MVP: Wohnungen Istrien)
URL = "https://www.njuskalo.hr/prodaja-stanova/istarska"
CSV_FILE = "njuskalo_daten.csv"

def run():
    # 1. Unsichtbaren Browser starten und Seite laden
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        html = page.content()
        browser.close()

    # 2. HTML auswerten
    soup = BeautifulSoup(html, "html.parser")
    inserate = soup.find_all("li", class_="EntityList-item")

    heute = datetime.now().strftime("%Y-%m-%d")
    neue_daten = []

    for item in inserate:
        try:
            article = item.find("article")
            if not article: continue
            
            oglas_id = article.get("data-ad-id", "N/A")
            title_tag = article.find("h3", class_="entity-title")
            title = title_tag.text.strip() if title_tag else ""
            
            price_tag = article.find("strong", class_="price")
            price = price_tag.text.strip() if price_tag else ""
            
            if oglas_id != "N/A" and title:
                neue_daten.append({
                    "ID": oglas_id,
                    "Titel": title,
                    "Preis": price,
                    "Datum_entdeckt": heute,
                    "Status": "Aktiv"
                })
        except Exception:
            continue

    df_neu = pd.DataFrame(neue_daten)
    if df_neu.empty:
        print("Keine Inserate gefunden.")
        return

    # 3. Historie abgleichen (Neu vs. Entfernt)
    if os.path.exists(CSV_FILE):
        df_alt = pd.read_csv(CSV_FILE)
        
        aktuelle_ids = df_neu["ID"].tolist()
        # Was heute fehlt, wird als 'Entfernt/Verkauft' markiert
        df_alt.loc[~df_alt["ID"].isin(aktuelle_ids), "Status"] = "Entfernt/Verkauft"
        
        # Neue Inserate anhängen
        alte_ids = df_alt["ID"].tolist()
        df_wirklich_neu = df_neu[~df_neu["ID"].isin(alte_ids)]
        df_final = pd.concat([df_alt, df_wirklich_neu], ignore_index=True)
    else:
        df_final = df_neu

    # 4. Automatische A-Z Sortierung anwenden
    df_final = df_final.sort_values(by=["Titel", "Preis"])

    # 5. Speichern
    df_final.to_csv(CSV_FILE, index=False, encoding="utf-8")
    print(f"Erfolgreich gespeichert. {len(df_neu)} aktuelle Inserate auf der ersten Seite verarbeitet.")

if __name__ == "__main__":
    run()
