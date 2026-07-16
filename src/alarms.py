import requests

FUSIONSOLAR_HOST = "https://eu5.fusionsolar.huawei.com"

def fetch_alarms(cookies, xsrf_token):
    """
    Recupera la lista degli allarmi attivi usando i cookie di sessione.
    """
    print("[*] Recupero degli allarmi attivi dal portale...")
    
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "XSRF-TOKEN": xsrf_token,
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Endpoint interno di Huawei per gli allarmi attivi
    url = f"{FUSIONSOLAR_HOST}/rest/pvms/v1/alarm/active-alarms"
    
    # Payload per richiedere la prima pagina degli allarmi
    payload = {
        "pageNo": 1,
        "pageSize": 50,
        "sortName": "raiseTime",
        "sortOrder": "desc"
    }

    try:
        response = requests.post(url, json=payload, cookies=cookies, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Estrae la lista degli allarmi dal JSON di risposta
            alarm_list = data.get("data", {}).get("list", [])
            print(f"[+] Recuperati {len(alarm_list)} allarmi.")
            return alarm_list
        else:
            print(f"[-] Errore risposta FusionSolar (Stato {response.status_code})")
            return []
    except Exception as e:
        print(f"[-] Impossibile recuperare gli allarmi: {e}")
        return []