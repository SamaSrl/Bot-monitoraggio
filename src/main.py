import os
from playwright.sync_api import sync_playwright

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
            print("[*] Compilazione login...")
            user_field = page.locator("input[name='ssoCredentials.username'], input[type='text']").first
            if not user_field.is_visible():
                page.mouse.click(850, 400)
                page.wait_for_timeout(500)
                
            user_field.fill(USERNAME, force=True)
            page.wait_for_timeout(500)

            pwd_field = page.locator("input[name='ssoCredentials.password'], input[type='password']").first
            pwd_field.fill(PASSWORD, force=True)
            page.wait_for_timeout(1000)

            # Selezione Region
            page.keyboard.press("Tab")
            page.wait_for_timeout(500)
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(500)
            page.keyboard.type("region004", delay=50)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            page.keyboard.press("Enter")
            page.mouse.click(1300, 400)
            
            # --- 2. ATTESA SCHERMATA PRINCIPALE ---
            print("[*] Attesa stabilizzazione Dashboard...")
            page.wait_for_load_state("networkidle", timeout=45000)
            page.wait_for_timeout(10000)

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

            # --- 4. SCANSIONE IMPIANTI ---
            print("[*] Avvio scansione colonna impianti...")
            
            impianti_trovati = {}
            blacklist = [
                "fusionsolar", "massimo soncin", "normale", "gestione energia", 
                "generata da fv:", "consumata (kwh)", "0,00 kwh", "kwh", "panoramica", 
                "layout", "andamento", "gestione dei report", "gestione del dispositivo", 
                "allarmi", "utenti dell'impianto", "resa di oggi", "consumo di oggi", 
                "autoconsumo", "resa totale", "home", "monitoraggio", "report", "impianti", 
                "servizi a valore aggiunto", "sistema", "kiosk", "inserisci un nome dispositivo"
            ]

            page.mouse.move(150, 300)

            for step in range(8):
                nodi = page.locator(".ant-tree-node-content-wrapper, .ant-tree-title, .nle-tree-node, [role='treeitem'], [title]").all()
                
                for nod in nodi:
                    try:
                        box = nod.bounding_box()
                        if not box or box['x'] > 380 or box['width'] == 0:
                            continue

                        title_attr = nod.get_attribute("title") or ""
                        text_val = nod.inner_text().strip()
                        nome = (title_attr if title_attr else text_val).split("\n")[0].strip()

                        if nome and len(nome) > 2 and not any(bad in nome.lower() for bad in blacklist):
                            if nome not in impianti_trovati:
                                parent_html = nod.locator("xpath=..").inner_html().lower()
                                
                                stato = "✅ OK"
                                if "red" in parent_html or "alarm" in parent_html or "fail" in parent_html:
                                    stato = "🚨 ALLARME CRITICO"
                                elif "yellow" in parent_html or "warn" in parent_html:
                                    stato = "⚠️ AVVISO"
                                elif "gray" in parent_html or "offline" in parent_html:
                                    stato = "⚪ OFFLINE"

                                impianti_trovati[nome] = stato
                    except Exception:
                        continue

                page.mouse.wheel(0, 350)
                page.wait_for_timeout(800)

            # SALVA SCREENSHOT GARANTITO
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' salvato con successo.")

            # --- 5. GENERAZIONE REPORT MD ---
            report_content = "# 📋 REPORT MONITORAGGIO IMPIANTI FUSIONSOLAR\n\n"
            report_content += "Questo file viene aggiornato automaticamente ad ogni esecuzione.\n\n"
            report_content += "| # | Nome Impianto | Stato |\n"
            report_content += "|---|----------------|-------|\n"

            if impianti_trovati:
                for idx, (nome, stato) in enumerate(impianti_trovati.items(), 1):
                    report_content += f"| {idx} | **{nome}** | {stato} |\n"
            else:
                report_content += "| - | *Nessun impianto rilevato* | - |\n"

            with open("REPORT_ALLARMI.md", "w", encoding="utf-8") as f:
                f.write(report_content)

            print(f"[+] Generato REPORT_ALLARMI.md con {len(impianti_trovati)} impianti.")
            browser.close()

        except Exception as e:
            print(f"[-] Errore durante l'esecuzione: {e}")
            page.screenshot(path="dashboard_check.png")
            browser.close()
            raise e

if __name__ == "__main__":
    main()
