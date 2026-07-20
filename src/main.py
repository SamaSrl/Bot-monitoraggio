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

    print("[*] Avvio Bot Monitoraggio FusionSolar...")
    
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
            print("[*] Attesa caricamento Dashboard...")
            page.wait_for_load_state("networkidle", timeout=45000)
            page.wait_for_timeout(8000)

            # --- 3. RIMOZIONE POPUP ---
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

            # --- 4. SCROLL DELLA LISTA & SCANSIONE IMPIANTI ---
            print("[*] Avvio scansione dinamica con scroll della lista...")
            
            impianti_trovati = {}  # Dizionario {NomeImpianto: Stato}
            
            # Posizioniamo il mouse sopra il pannello sinistro (es. coordinate X=150, Y=300) per attivare lo scroll
            page.mouse.move(150, 300)
            
            esclusi = [
                "Panoramica", "Layout", "Andamento", "Gestione dei report", "Gestione del dispositivo", 
                "Allarmi", "Utenti dell'impianto", "Resa di oggi", "Consumo di oggi", "Autoconsumo", 
                "Resa totale", "Home", "Monitoraggio", "Report", "Impianti", "Servizi a valore aggiunto", 
                "Sistema", "Kiosk", "Inserisci un nome dispositivo", "Prova la nuova versione"
            ]

            # Effettuiamo più passaggi di scroll per caricare tutta la virtual list
            for i in range(10):
                # Cerchiamo gli elementi visibili nella sidebar
                elementi = page.locator(".ant-tree-title, .ant-tree-node-content-wrapper, [title]").all()
                
                for el in elementi:
                    try:
                        box = el.bounding_box()
                        if not box or box['x'] > 380 or box['width'] == 0:
                            continue

                        # Estraiamo il nome dell'impianto
                        title_attr = el.get_attribute("title") or ""
                        text_content = el.inner_text().strip()
                        nome = (title_attr if title_attr else text_content).split("\n")[0].strip()

                        if nome and len(nome) > 2 and nome not in esclusi:
                            if nome not in impianti_trovati:
                                # Verifichiamo lo stato dell'icona/pallino vicino all'impianto
                                html_nodo = el.inner_html().lower()
                                parent_html = el.locator("xpath=..").inner_html().lower()
                                
                                stato = "✅ OK"
                                if "red" in parent_html or "alarm" in parent_html or "fail" in parent_html or "errore" in parent_html:
                                    stato = "🚨 ALLARME CRITICO"
                                elif "yellow" in parent_html or "warn" in parent_html:
                                    stato = "⚠️ AVVISO"
                                elif "gray" in parent_html or "offline" in parent_html or "disconnesso" in parent_html:
                                    stato = "⚪ OFFLINE"

                                impianti_trovati[nome] = stato
                    except Exception:
                        continue
                
                # Scroll verso il basso con la rotellina del mouse sulla colonna sinistra
                page.mouse.wheel(0, 400)
                page.wait_for_timeout(1000)

            # --- 5. GENERAZIONE REPORT ---
            report_content = "# 📋 REPORT MONITORAGGIO IMPIANTI FUSIONSOLAR\n\n"
            report_content += "Questo file viene aggiornato automaticamente ad ogni esecuzione.\n\n"
            report_content += "| # | Nome Impianto | Stato |\n"
            report_content += "|---|----------------|-------|\n"

            print("\n" + "="*60)
            print("                 REPORT STATO IMPIANTI")
            print("="*60)

            if impianti_trovati:
                for idx, (nome, stato) in enumerate(impianti_trovati.items(), 1):
                    print(f"🔹 Impianto {idx}: {nome}")
                    print(f"   Stato:      {stato}")
                    print("-" * 40)
                    report_content += f"| {idx} | **{nome}** | {stato} |\n"
            else:
                report_content += "| - | *Nessun impianto rilevato* | - |\n"

            print("="*60)
            print(f"[+] Trovati ed elaborati {len(impianti_trovati)} impianti in totale.")

            with open("REPORT_ALLARMI.md", "w", encoding="utf-8") as f:
                f.write(report_content)
            print("[+] File REPORT_ALLARMI.md salvato con successo!")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'estrazione dati: {e}")
            page.screenshot(path="error_data_screenshot.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
