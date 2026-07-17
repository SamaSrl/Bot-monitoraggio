import os
import csv
from playwright.sync_api import sync_playwright
 
# Host regionale predefinito
FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"
 
 
def get_fusionsolar_session(username, password, extract_errors=True, output_csv="errori_impianti.csv"):
    """
    Esegue il login, gestisce il popup di benvenuto e (opzionalmente) estrae
    la lista degli errori/allarmi degli impianti in un CSV.
    """
    print("[*] Avvio del browser in modalità simulazione hardware (Fix Regione via TAB)...")
 
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT,it;q=0.9",
            timezone_id="Europe/Rome",
            accept_downloads=True,
        )
 
        page = context.new_page()
 
        try:
            print(f"[*] Navigazione su {FUSIONSOLAR_HOST}...")
            page.goto(f"{FUSIONSOLAR_HOST}/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(8000)
 
            # --- 1. COMPILAZIONE USERNAME ---
            print("[*] Inserimento Username...")
            page.mouse.move(850, 400)
            page.mouse.click(850, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(username, delay=100)
            page.wait_for_timeout(1000)
 
            # --- 2. COMPILAZIONE PASSWORD ---
            print("[*] Inserimento Password...")
            page.mouse.move(1070, 400)
            page.mouse.click(1070, 400)
            page.wait_for_timeout(500)
            page.keyboard.type(password, delay=100)
            page.wait_for_timeout(3000)  # Aspettiamo che appaia visivamente il box region
 
            # --- 3. SPOSTAMENTO SU REGIONE VIA TAB ---
            print("[*] Navigazione sulla tendina della regione tramite tasto TAB...")
            page.keyboard.press("Tab")
            page.wait_for_timeout(1000)
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(1000)
 
            print("[*] Forzatura scrittura region004...")
            page.keyboard.type("region004", delay=150)
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
 
            # --- 4. CLICK SU ACCEDI VIA COORD/ENTER ---
            print("[*] Invio del modulo di login...")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
 
            print("[*] Clic di backup sul pulsante Accedi...")
            page.mouse.click(1300, 400)
 
            # --- 5. VERIFICA DASHBOARD ---
            print("[*] Attesa caricamento della Dashboard...")
            page.wait_for_selector("text=Monitoraggio, text=Impianti, .ant-layout", timeout=45000)
            print("[+] Accesso alla Dashboard confermato!")
            page.wait_for_timeout(4000)
 
            # --- 6. GESTIONE POPUP DI BENVENUTO E BANNER COOKIE (FIX) ---
            _close_cookie_banner(page)
            _close_welcome_popup(page)
 
            # --- 7. ESTRAZIONE cookie di sessione ---
            cookies = context.cookies()
            session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
            xsrf_token = ""
            for cookie in cookies:
                if cookie['name'] == 'XSRF-TOKEN':
                    xsrf_token = cookie['value']
                    break
            print("[+] Sessione catturata con successo!")
 
            # --- 8. ESTRAZIONE ERRORI/ALLARMI IMPIANTI ---
            if extract_errors:
                try:
                    extract_plant_errors(page, output_csv)
                except Exception as e:
                    # Non facciamo fallire l'intera sessione se l'estrazione
                    # errori fallisce: i cookie sono già stati catturati.
                    print(f"[-] Estrazione errori fallita (sessione comunque valida): {e}")
 
            browser.close()
            return session_cookies, xsrf_token
 
        except Exception as e:
            print(f"[-] Errore durante la sessione: {e}")
            try:
                page.screenshot(path="error_screenshot.png", full_page=True)
                print("[*] Screenshot di controllo salvato: error_screenshot.png")
                with open("error_dom_dump.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("[*] Dump HTML salvato: error_dom_dump.html")
            except Exception as dump_err:
                print(f"[-] Impossibile salvare screenshot/dump: {dump_err}")
 
            browser.close()
            raise e
 
 
def _close_cookie_banner(page, timeout_ms=4000):
    """
    Chiude il banner cookie in basso alla pagina ("Questo sito Web utilizza
    i cookie..."), se presente. Viene chiuso PRIMA del popup modale, perché
    può restare visibile e intercettare click successivi (es. in fase di
    scraping/paginazione della tabella errori).
    """
    print("[*] Controllo banner cookie...")
    try:
        # Cerchiamo un pulsante di chiusura/accetta vicino al testo del banner
        banner = page.locator(
            "text=Questo sito Web utilizza i cookie"
        ).first
        banner.wait_for(state="visible", timeout=timeout_ms)
 
        # Proviamo prima un eventuale pulsante esplicito (Accetta/Chiudi/OK)
        close_btn = page.locator(
            "button:has-text('Accetta'), button:has-text('Chiudi'), button:has-text('OK'), "
            ".cookie-consent button, [class*='cookie'] button"
        ).first
        try:
            close_btn.wait_for(state="visible", timeout=2000)
            close_btn.click(timeout=3000)
        except Exception:
            # Fallback: icona "X" generica vicino al banner
            page.locator("[class*='cookie'] .close, [class*='cookie'] [aria-label='close']").first.click(timeout=3000)
 
        page.wait_for_timeout(500)
        print("[+] Banner cookie chiuso.")
    except Exception as e:
        print(f"[*] Nessun banner cookie rilevato o già chiuso ({type(e).__name__}).")
 
 
def _close_welcome_popup(page, timeout_ms=8000, max_attempts=2):
    """
    Chiude il popup di benvenuto ("Aggiornamento della funzione") se presente.
    Usa get_by_role per un match affidabile sul nome accessibile del bottone,
    verifica che il popup sia EFFETTIVAMENTE scomparso dopo il click, e in
    caso di fallimento stampa l'errore reale invece di ignorarlo.
    """
    print("[*] Controllo eventuale popup di benvenuto...")
 
    for attempt in range(1, max_attempts + 1):
        try:
            # Il modale FusionSolar usa tipicamente ant-design: .ant-modal
            modal = page.locator(".ant-modal, [role='dialog']").first
            modal.wait_for(state="visible", timeout=timeout_ms)
            print(f"[+] Popup rilevato (tentativo {attempt}). Chiusura in corso...")
        except Exception:
            print("[*] Nessun popup rilevato (o già chiuso).")
            return
 
        closed = False
 
        # 1) Bottone "Non mostrare di nuovo" (match sul nome accessibile esatto)
        try:
            btn = page.get_by_role("button", name="Non mostrare di nuovo")
            btn.click(timeout=4000)
            page.wait_for_timeout(1000)
            closed = True
        except Exception as e:
            print(f"[-] Click su 'Non mostrare di nuovo' fallito: {e}")
 
        # 2) Fallback: icona X di chiusura del modale
        if not closed:
            try:
                page.locator(".ant-modal-close").first.click(timeout=4000, force=True)
                page.wait_for_timeout(1000)
                closed = True
            except Exception as e:
                print(f"[-] Click su icona di chiusura fallito: {e}")
 
        # 3) Fallback finale: tasto Escape
        if not closed:
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[-] Escape fallito: {e}")
 
        # Verifica che il modale sia davvero sparito
        try:
            page.locator(".ant-modal, [role='dialog']").first.wait_for(state="hidden", timeout=4000)
            print("[+] Popup chiuso con successo.")
            return
        except Exception:
            print(f"[-] Popup ancora presente dopo tentativo {attempt}.")
 
    print("[!] Impossibile chiudere il popup dopo tutti i tentativi. Proseguo comunque.")
 
 
def extract_plant_errors(page, output_csv="errori_impianti.csv"):
    """
    Naviga alla sezione Allarmi/Guasti e prova a estrarre gli errori.
    Strategia:
      1. Tenta di cliccare la voce di menu Allarmi/Guasti/Errori.
      2. Se esiste un pulsante di esportazione, lo usa e scarica il file.
      3. Altrimenti fa scraping della tabella a video, con paginazione.
 
    NB: i selettori esatti dipendono dalla versione dell'interfaccia
    FusionSolar del tuo tenant. Se questa funzione non trova nulla,
    guarda 'menu_dump.png' e 'menu_dom_dump.html' generati qui sotto
    per identificare i testi/selettori corretti e aggiornali.
    """
    print("[*] Ricerca della sezione Allarmi/Guasti/Errori...")
 
    menu_candidates = [
        "text=Guasti",
        "text=Allarmi",
        "text=Errori",
        "text=Alarm",
        "text=Fault",
    ]
 
    opened = False
    for candidate in menu_candidates:
        try:
            loc = page.locator(candidate).first
            loc.wait_for(state="visible", timeout=3000)
            loc.click()
            page.wait_for_timeout(3000)
            opened = True
            print(f"[+] Sezione aperta tramite selettore: {candidate}")
            break
        except Exception:
            continue
 
    if not opened:
        print("[-] Non ho trovato automaticamente la voce di menu Allarmi/Guasti.")
        page.screenshot(path="menu_dump.png", full_page=True)
        with open("menu_dom_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("[*] Salvati menu_dump.png e menu_dom_dump.html per ispezione manuale.")
        return
 
    # --- Tentativo 1: pulsante di esportazione nativo ---
    export_candidates = ["text=Esporta", "text=Export", "button:has-text('Esporta')"]
    for candidate in export_candidates:
        try:
            export_btn = page.locator(candidate).first
            export_btn.wait_for(state="visible", timeout=3000)
            with page.expect_download(timeout=20000) as download_info:
                export_btn.click()
            download = download_info.value
            download.save_as(output_csv.replace(".csv", "_export" + os.path.splitext(download.suggested_filename)[1]))
            print(f"[+] File esportato salvato come: {download.suggested_filename}")
            return
        except Exception:
            continue
 
    # --- Tentativo 2: scraping della tabella a video ---
    print("[*] Nessun pulsante di export trovato, provo lo scraping della tabella...")
    try:
        page.wait_for_selector("table, .ant-table", timeout=10000)
    except Exception:
        print("[-] Nessuna tabella trovata nella pagina Allarmi/Guasti.")
        page.screenshot(path="table_dump.png", full_page=True)
        return
 
    rows_data = []
    headers = []
    page_num = 1
    max_pages = 50  # sicurezza anti-loop infinito
 
    while page_num <= max_pages:
        # Header (solo alla prima pagina)
        if not headers:
            header_cells = page.locator(".ant-table-thead th").all_inner_texts()
            if header_cells:
                headers = [h.strip() for h in header_cells]
 
        # Righe della tabella corrente
        row_locators = page.locator(".ant-table-tbody tr")
        row_count = row_locators.count()
        for i in range(row_count):
            cells = row_locators.nth(i).locator("td").all_inner_texts()
            if cells:
                rows_data.append([c.strip() for c in cells])
 
        print(f"[*] Pagina {page_num}: estratte {row_count} righe (totale finora: {len(rows_data)}).")
 
        # Prova ad andare alla pagina successiva
        next_btn = page.locator(".ant-pagination-next").first
        try:
            is_disabled = next_btn.get_attribute("aria-disabled")
            if is_disabled == "true":
                break
            next_btn.click()
            page.wait_for_timeout(2000)
            page_num += 1
        except Exception:
            break
 
    if rows_data:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows_data)
        print(f"[+] Salvate {len(rows_data)} righe di errori in: {output_csv}")
    else:
        print("[-] Nessuna riga estratta dalla tabella.")
 
 
if __name__ == "__main__":
    user = os.environ.get("FUSIONSOLAR_USER", "")
    pwd = os.environ.get("FUSIONSOLAR_PASS", "")
    if not user or not pwd:
        print("[-] Imposta le variabili d'ambiente FUSIONSOLAR_USER e FUSIONSOLAR_PASS.")
    else:
        get_fusionsolar_session(user, pwd)