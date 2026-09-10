import os
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import time

# Die Liste aller Küstenregionen (Häuser & Wohnungen)
URLS = [
    {"url": "https://www.njuskalo.hr/prodaja-stanova/istarska", "Region": "Istrien", "Typ": "Wohnung"},
    {"url": "https://www.njuskalo.hr/prodaja-kuca/istarska", "Region": "Istrien", "Typ": "Haus"},
    {"url": "https://www.njuskalo.hr/prodaja-stanova/primorsko-goranska", "Region": "Kvarner", "Typ": "Wohnung"},
    {"url": "https://www.njuskalo.hr/prodaja-kuca/primorsko-goranska", "Region": "Kvarner", "Typ": "Haus"},
    {"url": "https://www.njuskalo.hr/prodaja-stanova/zadarska", "Region": "Zadar", "Typ": "Wohnung"},
    {"url": "https://www.njuskalo.hr/prodaja-kuca/zadarska", "Region": "Zadar", "Typ": "Haus"},
    {"url": "https://www.njuskalo.hr/prodaja-stanova/splitsko-dalmatinska", "Region": "Split-Dalmatien", "Typ": "Wohnung"},
    {"url": "https://www.njuskalo.hr/prodaja-kuca/splitsko-dalmatinska", "Region": "Split-Dalmatien", "Typ": "Haus"}
]

CSV_FILE = "njuskalo_kueste_daten.csv"

def run():
    heute = datetime.now().strftime("%Y-%m-%d")
    neue_daten = []

    with sync_playwright() as p:
        # 1. Tarnung für den Bot aktivieren (User-Agent + Flags)
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # Schleife: Jede URL nacheinander abrufen
        for ziel in URLS:
            try:
                print(f"Scrape {ziel['Typ']} in {ziel['Region']}...")
                
                # 2. Timeout erhöhen und 'domcontentloaded' statt 'networkidle' nutzen
                page.goto(ziel['url'], wait_until="domcontentloaded", timeout=60000)
                
                # 3. Explizit warten, bis die Inserate im HTML auftauchen (max 15 Sek)
                page.wait_for_selector("li.EntityList-item", timeout=15000)
                
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                inserate = soup.find_all("li", class_="EntityList-item")

                for item in inserate:
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
                            "Region": ziel['Region'],
                            "Typ": ziel['Typ'],
                            "Datum_entdeckt": heute,
                            "Status": "Aktiv"
                        })
                
                # Kurze Pause, um den Njuškalo-Server nicht zu überlasten
                time.sleep(3) 
            except Exception as e:
                print(f"Fehler bei {ziel['url']}: {e}")
                continue

        browser.close()

    df_neu = pd.DataFrame(neue_daten)
    if df_neu.empty:
        print("Keine Inserate gefunden.")
        return

    # Historie abgleichen (Neu vs. Entfernt)
    if os.path.exists(CSV_FILE):
        df_alt = pd.read_csv(CSV_FILE)
        
        aktuelle_ids = df_neu["ID"].tolist()
        df_alt.loc[~df_alt["ID"].isin(aktuelle_ids), "Status"] = "Entfernt/Verkauft"
        
        alte_ids = df_alt["ID"].tolist()
        df_wirklich_neu = df_neu[~df_neu["ID"].isin(alte_ids)]
        df_final = pd.concat([df_alt, df_wirklich_neu], ignore_index=True)
    else:
        df_final = df_neu

    # Automatische A-Z Sortierung (erst nach Region, dann Typ, dann Titel)
    df_final = df_final.sort_values(by=["Region", "Typ", "Titel"])

    # Speichern
    df_final.to_csv(CSV_FILE, index=False, encoding="utf-8")
    print(f"Erfolgreich gespeichert. {len(df_neu)} aktive Inserate insgesamt verarbeitet.")

if __name__ == "__main__":
    run()
