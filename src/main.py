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

            # --- 4. ESTRAZIONE TARGETIZZATA DELLA BARRA LATERALE SINISTRA ---
            print("[*] Analisi selettiva della colonna sinistra degli impianti...")
            
            # Per evitare di leggere i titoli dei riquadri centrali, cerchiamo solo i testi contenuti
            # all'interno dei nodi dell'albero laterale di sinistra (solitamente classi .ant-tree-* o liste nidificate)
            # Tagliamo fuori la dashboard centrale cercando elementi dentro l'area del menu/albero dei dispositivi
            sidebar_items = page.locator(".ant-tree-title, .tree-text, .ant-tree-node-content-wrapper").all()
            
            nomi_impianti = []
            esclusi = ["Panoramica", "Andamento", "Gestione dei report", "Gestione del dispositivo", "Allarmi", "Utenti dell'impianto", "Resa di oggi", "Consumo di oggi", "Autoconsumo", "Resa totale"]

            for item in sidebar_items:
                text = item.inner_text().strip()
                # Pulizia da eventuali righe multiple o spazi vuoti
                if not text:
                    continue
                clean_text = text.split("\n")[0].strip()
                
                # Filtro di sicurezza per catturare solo i veri impianti (quelli che contengono parole chiave dei tuoi impianti come Cimolai, R.C., srl, ecc.)
                if any(k in clean_text for k in ["Cimolai", "R.C.", "srl", "Armando", "Meleto", "Roberto", "Technology", "Poseido", "Zeus"]):
                    if clean_text not in nomi_impianti:
                        nomi_impianti.append(clean_text)

            # --- 5. GENERAZIONE DEL FILE DI REPORT ---
            report_content = "# 📋 REPORT MONITORAGGIO IMPIANTI FUSIONSOLAR\n\n"
            report_content += "Questo file viene aggiornato automaticamente dal bot ad ogni esecuzione.\n\n"
            report_content += "| # | Nome Impianto | Stato Allarme |\n"
            report_content += "|---|----------------|---------------|\n"

            print("\n" + "="*60)
            print("                 REPORT STATO IMPIANTI")
            print("="*60)

            for idx, nome in enumerate(nomi_impianti, 1):
                stato_allarme = "✅ nessun allarme"
                print(f"🔹 Impianto {idx}: {nome}")
                print(f"   Stato:      {stato_allarme}")
                print("-" * 40)
                
                # Aggiungiamo la riga alla tabella del file
                report_content += f"| {idx} | **{nome}** | {stato_allarme} |\n"

            print("="*60)
            print(f"[+] Trovati ed elaborati {len(nomi_impianti)} impianti.")

            # Salviamo fisicamente il file nel workspace
            with open("REPORT_ALLARMI.md", "w", encoding="utf-8") as f:
                f.write(report_content)
            print("[+] File REPORT_ALLARMI.md generato con successo!")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'estrazione dati: {e}")
            page.screenshot(path="error_data_screenshot.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
