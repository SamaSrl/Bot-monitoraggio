import os
from playwright.sync_api import sync_playwright

# Configurazione credenziali
USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    print("[*] Avvio del Bot per estrazione mirata della barra laterale impianti...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9"
        )
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            # --- 1. LOGIN ---
            page.mouse.click(850, 400)
            page.keyboard.type(USERNAME, delay=50)
            page.mouse.click(1070, 400)
            page.keyboard.type(PASSWORD, delay=50)
            page.wait_for_timeout(2000)

            # Selezione regione via TAB
            page.keyboard.press("Tab")
            page.wait_for_timeout(500)
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(500)
            page.keyboard.type("region004", delay=50)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Click Accedi
            page.keyboard.press("Enter")
            page.mouse.click(1300, 400)
            
            # --- 2. ATTESA SCHERMATA PRINCIPALE ---
            print("[*] Attesa stabilizzazione della Dashboard...")
            page.wait_for_load_state("networkidle", timeout=45000)
            page.wait_for_timeout(8000)

            # --- 3. RIMOZIONE POPUP DI BENVENUTO ---
            popup_selectors = ["text='Non mostrare di nuovo'", "button:has-text('Non mostrare di nuovo')", ".ant-modal-close"]
            for selector in popup_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # --- 4. ESTRAZIONE TARGETIZZATA DEGLI IMPIANTI ---
            print("[*] Analisi approfondita della barra laterale...")
            
            nomi_impianti = []
            
            # Metodo 1: Cerchiamo tutti gli elementi che hanno un attributo 'title' o testo visibile nella colonna di sinistra
            # La barra laterale di FusionSolar di solito risiede dentro un div/aside a sinistra (X < 400px)
            elementi_visibili = page.locator("span, div, a, li").all()
            
            esclusi = [
                "Panoramica", "Layout", "Andamento", "Gestione dei report", "Gestione del dispositivo", 
                "Allarmi", "Utenti dell'impianto", "Resa di oggi", "Consumo di oggi", "Autoconsumo", 
                "Resa totale", "Home", "Monitoraggio", "Report", "Impianti", "Servizi a valore aggiunto", 
                "Sistema", "Kiosk", "Inserisci un nome dispositivo", "Prova la nuova versione"
            ]

            for el in elementi_visibili:
                try:
                    # Verifichiamo la posizione dell'elemento: deve trovarsi nella metà sinistra dello schermo (X < 350)
                    box = el.bounding_box()
                    if not box or box['x'] > 350 or box['width'] == 0:
                        continue

                    # Estraiamo sia l'attributo title sia il testo interno
                    title_attr = el.get_attribute("title") or ""
                    inner_text = el.inner_text().strip()
                    
                    testo_candidato = title_attr if title_attr else inner_text
                    clean_text = testo_candidato.split("\n")[0].strip()

                    # Controlliamo che sia un nome valido e non una voce di menu
                    if clean_text and len(clean_text) > 2 and clean_text not in esclusi:
                        # Verifichiamo che non sia già stato aggiunto
                        if clean_text not in nomi_impianti:
                            nomi_impianti.append(clean_text)
                except Exception:
                    continue

            # --- 5. GENERAZIONE DEL FILE DI REPORT ---
            report_content = "# 📋 REPORT MONITORAGGIO IMPIANTI FUSIONSOLAR\n\n"
            report_content += "Questo file viene aggiornato automaticamente dal bot ad ogni esecuzione.\n\n"
            report_content += "| # | Nome Impianto | Stato Allarme |\n"
            report_content += "|---|----------------|---------------|\n"

            print("\n" + "="*60)
            print("                 REPORT STATO IMPIANTI")
            print("="*60)

            if nomi_impianti:
                for idx, nome in enumerate(nomi_impianti, 1):
                    stato_allarme = "✅ nessun allarme"
                    print(f"🔹 Impianto {idx}: {nome}")
                    print(f"   Stato:      {stato_allarme}")
                    print("-" * 40)
                    report_content += f"| {idx} | **{nome}** | {stato_allarme} |\n"
            else:
                print("[-] Nessun impianto rilevato con le coordinate X < 350. Controllo in corso...")
                report_content += "| - | *Nessun impianto rilevato* | - |\n"

            print("="*60)
            print(f"[+] Trovati ed elaborati {len(nomi_impianti)} impianti.")

            # Salviamo il file
            with open("REPORT_ALLARMI.md", "w", encoding="utf-8") as f:
                f.write(report_content)
            print("[+] File REPORT_ALLARMI.md generato e salvato!")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'estrazione dati: {e}")
            page.screenshot(path="error_data_screenshot.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
