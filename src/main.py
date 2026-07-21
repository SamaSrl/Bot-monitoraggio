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
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT"
        )
        
        page = context.new_page()

        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            # Cerca il frame UniSSO
            target = page
            for frame in page.frames:
                if "unisso" in frame.url or frame.locator("input[type='password']").count() > 0:
                    target = frame
                    print(f"[+] Frame UniSSO agganciato: {frame.url}")
                    break

            # --- STEP 1: USERNAME ---
            print("[*] Compilazione Username...")
            user_el = target.locator("input[type='text']:visible, input[placeholder*='utente']:visible").first
            user_el.wait_for(state="visible", timeout=10000)
            user_el.click()
            user_el.fill(USERNAME)
            
            # --- STEP 2: PASSWORD ---
            print("[*] Compilazione Password...")
            pwd_el = target.locator("input[type='password']").first
            pwd_el.wait_for(state="attached", timeout=10000)

            page.keyboard.press("Tab")
            page.wait_for_timeout(200)
            page.keyboard.type(PASSWORD, delay=30)
            page.wait_for_timeout(200)

            target.evaluate("""
                (pwdValue) => {
                    const pwdInput = document.querySelector("input[type='password']");
                    if (pwdInput) {
                        pwdInput.value = pwdValue;
                        pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
                        pwdInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            """, PASSWORD)
            page.wait_for_timeout(500)

            # --- STEP 3: SELEZIONE REGION 004 (ELEMENT UI DROPDOWN) ---
            print("[*] Apertura menu Selezione Region...")
            try:
                # Clicca sul box del selettore region
                region_box = target.locator("input[readonly], .el-select, .select-region, div:has-text('region003')").first
                region_box.click(force=True)
                page.wait_for_timeout(1000)

                # Cerca l'opzione region004 nell'elenco a comparsa (può essere sia nell'iframe che nella pagina madre)
                print("[*] Selezione 'region004'...")
                opt_004 = target.locator("li:has-text('region004'), span:has-text('region004'), div:has-text('region004')").first
                
                if opt_004.is_visible():
                    opt_004.click(force=True)
                    print("[+] Region 004 selezionata!")
                else:
                    # Se l'elenco si apre nel documento principale
                    page.locator("li:has-text('region004'), span:has-text('region004')").first.click(force=True)
                    print("[+] Region 004 selezionata dal documento principale!")
            except Exception as reg_err:
                print(f"[!] Avviso selezione region: {reg_err}")

            page.wait_for_timeout(1000)

            # Screenshot di verifica prima del click finale
            page.screenshot(path="pre_login_check.png")

            # --- STEP 4: CLICK PULSANTE ACCEDI ---
            print("[*] Esecuzione Click su 'Accedi'...")
            
            # Troviamo il pulsante 'Accedi' e facciamo click con Javascript + Playwright
            login_success = target.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, div, span, a'));
                    const btn = buttons.find(b => b.innerText && b.innerText.trim() === 'Accedi');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                }
            """)

            if not login_success:
                print("[!] Click JS fallito, eseguo click fisico sul pulsante...")
                btn_acc = target.locator("button:has-text('Accedi'), .login-btn, input[type='submit']").first
                btn_acc.click(force=True)

            print("[*] Attesa caricamento Dashboard...")
            page.wait_for_timeout(20000)

            # Screenshot Finale della Dashboard
            page.screenshot(path="dashboard_check.png")
            print("[+] Screenshot 'dashboard_check.png' generato con successo!")

        except Exception as e:
            print(f"[-] Errore catturato durante la procedura: {e}")
            page.screenshot(path="dashboard_check.png")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
