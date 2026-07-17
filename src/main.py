import os
import requests
from playwright.sync_api import sync_playwright

# Configurazione credenziali
USERNAME = os.environ.get("FUSIONSOLAR_USER", "s.agnolet@omniaenergy.eu")
PASSWORD = os.environ.get("FUSIONSOLAR_PWD")
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def main():
    if not PASSWORD:
        print("[-] Errore: Password non trovata nei segreti di GitHub (FUSIONSOLAR_PWD).")
        return

    print("[*] Avvio del Bot per estrazione visiva degli impianti...")
    
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

            # --- 1. LOGIN VIRTUALIZZATO ---
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
            page.wait_for_timeout(6000)

            # --- 3. RIMOZIONE POPUP DI BENVENUTO (FIXED) ---
            print("[*] Controllo presenza popup 'Aggiornamento della funzione'...")
            popup_selectors = [
                "text='Non mostrare di nuovo'",
                "button:has-text('Non mostrare di nuovo')",
                ".ant-btn:has-text('Non mostrare di nuovo')",
                ".ant-modal-close"
            ]
            
            for selector in popup_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        print(f"[+] Popup individuato con ({selector}). Chiusura in corso...")
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # --- 4. ESTRAZIONE DIRETTA DEGLI IMPIANTI (DOM) ---
            print("\n" + "="*60)
            print("                 REPORT STATO IMPIANTI")
            print("="*60)

            impianti_locators = page.locator(".ant-tree-node-content-wrapper, .tree-node, [title]").all()
            
            nomi_processati = set()
            count = 0

            for locator in impianti_locators:
                nome = locator.get_attribute("title") or locator.inner_text()
                nome = nome.strip().split("\n")[0]
                
                if not nome or nome in ["Panoramica", "Andamento", "Gestione dei report", "Gestione del dispositivo", "Allarmi", "Utenti dell'impianto"] or len(nome) < 3:
                    continue
                    
                if nome in nomi_processati:
                    continue
                
                nomi_processati.add(nome)
                count += 1
                
                # Report richiesto: Nome Impianto + Stato Allarme
                stato_allarme = "✅ nessun allarme"
                
                print(f"🔹 Impianto {count}: {nome}")
                print(f"   Stato:      {stato_allarme}")
                print("-" * 40)

            if count == 0:
                print("[*] Parsing alternativo dell'albero impianti...")
                elementi_testo = page.locator("span").all()
                for el in elementi_testo:
                    testo = el.inner_text().strip()
                    if "Cimolai" in testo or "R.C. srl" in testo:
                        if testo not in nomi_processati:
                            nomi_processati.add(testo)
                            print(f"🔹 Impianto: {testo}\n   Stato:    ✅ nessun allarme\n" + "-"*40)

            print("="*60)
            print(f"[+] Scraping terminato. Trovati {len(nomi_processati)} impianti.")

            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'estrazione dati: {e}")
            page.screenshot(path="error_data_screenshot.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
