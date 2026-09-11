import os
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import time

# Die Liste für Index Oglasi (Alle vier Küstenregionen)
URLS = [
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-stanova/istarska-zupanija/pretraga", "Region": "Istrien", "Typ": "Wohnung"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-kuca/istarska-zupanija/pretraga", "Region": "Istrien", "Typ": "Haus"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-stanova/primorsko-goranska-zupanija/pretraga", "Region": "Kvarner", "Typ": "Wohnung"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-kuca/primorsko-goranska-zupanija/pretraga", "Region": "Kvarner", "Typ": "Haus"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-stanova/zadarska-zupanija/pretraga", "Region": "Zadar", "Typ": "Wohnung"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-kuca/zadarska-zupanija/pretraga", "Region": "Zadar", "Typ": "Haus"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-stanova/splitsko-dalmatinska-zupanija/pretraga", "Region": "Split-Dalmatien", "Typ": "Wohnung"},
    {"url": "https://www.index.hr/oglasi/nekretnine/prodaja-kuca/splitsko-dalmatinska-zupanija/pretraga", "Region": "Split-Dalmatien", "Typ": "Haus"}
]

CSV_FILE = "index_kueste_daten.csv"

def run():
    heute = datetime.now().strftime("%Y-%m-%d")
    neue_daten_dict = {} # Verhindert doppelte Einträge

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        for ziel in URLS:
            try:
                print(f"Scrape {ziel['Typ']} in {ziel['Region']} auf Index.hr...")
                
                page.goto(ziel['url'], wait_until="domcontentloaded", timeout=60000)
                # Wir warten, bis mindestens ein Link zu einem Oglas (Inserat) geladen ist
                page.wait_for_selector("a[href*='/oglas/']", timeout=15000)
                
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Alle Links finden, die auf ein Inserat deuten
                inserate_links = soup.find_all("a", href=True)

                for link in inserate_links:
                    href = link['href']
                    if "/oglas/" not in href:
                        continue
                    
                    # ID aus der URL extrahieren (die Nummer am Ende des Links)
                    oglas_id = href.split("/")[-1].split("?")[0]
                    
                    # Manchmal gibt es mehrere Links zum selben Inserat (Bild, Titel). Wir nehmen jeden nur einmal.
                    if oglas_id not in neue_daten_dict and oglas_id.isdigit():
                        # Versuche den Preis zu finden (im Text des Links)
                        price_tag = link.find(string=lambda t: t and "€" in t)
                        price = price_tag.strip() if price_tag else "Auf Anfrage"
                        
                        # Versuche den Titel zu finden (meist als h3 formatiert)
                        title_tag = link.find("h3") or link.find(class_=lambda c: c and "title" in c.lower())
                        title = title_tag.text.strip() if title_tag else f"Inserat {oglas_id}"
                        
                        neue_daten_dict[oglas_id] = {
                            "ID": oglas_id,
                            "Titel": title,
                            "Preis": price,
                            "Region": ziel['Region'],
                            "Typ": ziel['Typ'],
                            "Datum_entdeckt": heute,
                            "Status": "Aktiv"
                        }
                
                time.sleep(3) 
            except Exception as e:
                print(f"Fehler bei {ziel['url']}: {e}")
                continue

        browser.close()

    neue_daten = list(neue_daten_dict.values())
    df_neu = pd.DataFrame(neue_daten)
    
    if df_neu.empty:
        print("Keine Inserate gefunden.")
        return

    # Historie abgleichen
    if os.path.exists(CSV_FILE):
        df_alt = pd.read_csv(CSV_FILE)
        
        aktuelle_ids = df_neu["ID"].tolist()
        df_alt.loc[~df_alt["ID"].astype(str).isin(aktuelle_ids), "Status"] = "Entfernt/Verkauft"
        
        alte_ids = df_alt["ID"].astype(str).tolist()
        df_wirklich_neu = df_neu[~df_neu["ID"].astype(str).isin(alte_ids)]
        df_final = pd.concat([df_alt, df_wirklich_neu], ignore_index=True)
    else:
        df_final = df_neu

    # Automatische A-Z Sortierung, wie wir es für CSV-Exporte vereinbart haben
    df_final = df_final.sort_values(by=["Region", "Typ", "Titel"])

    # Speichern
    df_final.to_csv(CSV_FILE, index=False, encoding="utf-8")
    print(f"Erfolgreich gespeichert. {len(df_neu)} aktive Inserate auf Index Oglasi verarbeitet.")

if __name__ == "__main__":
    run()
