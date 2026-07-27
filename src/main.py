import os
import requests
import json

# Credenziali dalle Environment Variables di GitHub
API_USER = os.environ.get("FUSIONSOLAR_API_USER", "")
API_KEY = os.environ.get("FUSIONSOLAR_API_KEY", "")

# Lista degli endpoint API FusionSolar Huawei
API_HOSTS = [
    "https://intl.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://eu5.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://uni001eu5.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://region003.fusionsolar.huawei.com/thirdstation/v1.0",
    "https://sg5.fusionsolar.huawei.com/thirdstation/v1.0"
]

def main():
    print("[*] Avvio generazione Web App...")

    # Diagnostica API FusionSolar
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    })

    success_host = None
    stations = []
    error_logs = []

    if API_USER and API_KEY:
        for host in API_HOSTS:
            payloads = [
                {"systemCode": API_USER, "secretKey": API_KEY},
                {"userName": API_USER, "value": API_KEY}
            ]
            for p_idx, payload in enumerate(payloads):
                try:
                    res = session.post(f"{host}/login", json=payload, timeout=10)
                    if res.status_code == 200:
                        try:
                            data = res.json()
                            if data.get("failCode") == 0 or data.get("success") is True:
                                success_host = host
                                xsrf = res.headers.get("XSRF-TOKEN")
                                if xsrf:
                                    session.headers.update({"XSRF-TOKEN": xsrf})
                                break
                            else:
                                error_logs.append(f"{host} (Payload {p_idx+1}): {data}")
                        except Exception:
                            error_logs.append(f"{host}: Risposta non JSON (404/HTML)")
                    else:
                        error_logs.append(f"{host}: Errore HTTP {res.status_code}")
                except Exception as e:
                    error_logs.append(f"{host}: {e}")

            if success_host:
                break

        if success_host:
            try:
                st_res = session.post(f"{success_host}/station/list", json={"pageNo": 1}, timeout=10)
                stations = st_res.json().get("data", [])
                session.post(f"{success_host}/logout", timeout=5)
            except Exception as e:
                error_logs.append(f"Errore lettura impianti: {e}")
    else:
        error_logs.append("Credenziali FUSIONSOLAR_API_USER o FUSIONSOLAR_API_KEY non trovate.")

    # Creazione della cartella 'public' per GitHub Pages
    os.makedirs("public", exist_ok=True)

    # Generazione dell'HTML con supporto per input coordinate dinamico
    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Impianto & Meteo Dinamico</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f1f5f9;
            color: #0f172a;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            background-color: #0f172a;
            color: #ffffff;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{ margin: 0 0 5px 0; font-size: 22px; }}
        .card {{
            background: #ffffff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .card-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            border-left: 4px solid #0284c7;
            padding-left: 10px;
        }}
        .input-group {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            align-items: center;
        }}
        .input-group label {{ font-weight: bold; font-size: 14px; }}
        .input-group input {{
            padding: 8px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            width: 130px;
            font-size: 14px;
        }}
        .btn {{
            background-color: #0284c7;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
        }}
        .btn:hover {{ background-color: #0369a1; }}
        .weather-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }}
        .weather-item {{
            background: #f8fafc;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            text-align: center;
        }}
        .weather-value {{
            font-size: 18px;
            font-weight: bold;
            color: #0284c7;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px;
            border-bottom: 1px solid #cbd5e1;
            text-align: left;
        }}
        th {{ background-color: #f8fafc; }}
        .badge-success {{ color: #15803d; font-weight: bold; }}
        .badge-danger {{ color: #b91c1c; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>☀️ Dashboard Monitoraggio & Meteo Localizzato</h1>
            <p style="margin:0; color:#94a3b8;">Inserisci le coordinate per visualizzare il meteo in tempo reale</p>
        </div>

        <!-- SEZIONE METEO CON INPUT MANUALE -->
        <div class="card">
            <div class="card-title">🌤️ Meteo del Giorno per Coordinate</div>
            
            <div class="input-group">
                <div>
                    <label for="lat">Latitudine:</label><br>
                    <input type="number" step="any" id="lat" value="45.4642" placeholder="es. 45.4642">
                </div>
                <div>
                    <label for="lon">Longitudine:</label><br>
                    <input type="number" step="any" id="lon" value="9.1900" placeholder="es. 9.1900">
                </div>
                <div style="align-self: flex-end;">
                    <button class="btn" onclick="fetchWeather()">Aggiorna Meteo</button>
                </div>
            </div>

            <div class="weather-grid">
                <div class="weather-item">
                    <div>Condizione</div>
                    <div class="weather-value" id="w-condition">In caricamento...</div>
                </div>
                <div class="weather-item">
                    <div>Temperatura</div>
                    <div class="weather-value" id="w-temp">-- °C</div>
                </div>
                <div class="weather-item">
                    <div>Vento</div>
                    <div class="weather-value" id="w-wind">-- km/h</div>
                </div>
            </div>
        </div>

        <!-- SEZIONE FUSIONSOLAR -->
        <div class="card">
            <div class="card-title">⚡ Stato API FusionSolar</div>
"""

    if success_host:
        html_content += f"""
            <p>Stato Connessione: <span class="badge-success">🟢 Connesso</span> (Server: <code>{success_host}</code>)</p>
            <h3>Impianti Rilevati ({len(stations)})</h3>
            <table>
                <tr>
                    <th>Nome Impianto</th>
                    <th>Codice Impianto</th>
                    <th>Capacità (kWp)</th>
                </tr>
        """
        if stations:
            for s in stations:
                html_content += f"""
                <tr>
                    <td><b>{s.get('stationName', 'N/D')}</b></td>
                    <td><code>{s.get('stationCode', 'N/D')}</code></td>
                    <td>{s.get('capacity', 'N/D')} kWp</td>
                </tr>
                """
        else:
            html_content += "<tr><td colspan='3'>Nessun impianto associato a questo account.</td></tr>"
        html_content += "</table>"
    else:
        html_content += """
            <p>Stato Connessione: <span class="badge-danger">🔴 Non Connesso</span></p>
            <h4>Log Tentativi:</h4>
            <ul>
        """
        for log in error_logs:
            html_content += f"<li><code>{log}</code></li>"
        html_content += "</ul>"

    html_content += """
        </div>
    </div>

    <!-- SCRIPT JAVASCRIPT PER CHIAMATA METEO AL VOLO -->
    <script>
        const weatherCodes = {
            0: "Cielo Sereno ☀️",
            1: "Prevalentemente Sereno 🌤️",
            2: "Parzialmente Nuvoloso ⛅",
            3: "Coperto ☁️",
            45: "Nebbia 🌫️",
            48: "Nebbia con Brina 🌫️",
            51: "Pioggerella Leggera 🌦️",
            61: "Pioggia Leggera 🌧️",
            63: "Pioggia Moderata 🌧️",
            65: "Pioggia Intensa 🌧️",
            80: "Rovesci di Pioggia 🌦️",
            95: "Temporale ⛈️"
        };

        window.onload = function() {
            const savedLat = localStorage.getItem("user_lat");
            const savedLon = localStorage.getItem("user_lon");
            if (savedLat) document.getElementById("lat").value = savedLat;
            if (savedLon) document.getElementById("lon").value = savedLon;
            
            fetchWeather();
        };

        async function fetchWeather() {
            const lat = document.getElementById("lat").value;
            const lon = document.getElementById("lon").value;

            if (!lat || !lon) {
                alert("Inserisci sia la Latitudine che la Longitudine!");
                return;
            }

            localStorage.setItem("user_lat", lat);
            localStorage.setItem("user_lon", lon);

            document.getElementById("w-condition").innerText = "Caricamento...";
            document.getElementById("w-temp").innerText = "--";
            document.getElementById("w-wind").innerText = "--";

            try {
                const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`;
                const response = await fetch(url);
                const data = await response.json();

                if (data.current_weather) {
                    const cw = data.current_weather;
                    const conditionText = weatherCodes[cw.weathercode] || "Variabile 🌤️";

                    document.getElementById("w-condition").innerText = conditionText;
                    document.getElementById("w-temp").innerText = cw.temperature + " °C";
                    document.getElementById("w-wind").innerText = cw.windspeed + " km/h";
                } else {
                    document.getElementById("w-condition").innerText = "Dati non trovati";
                }
            } catch (err) {
                console.error("Errore meteo:", err);
                document.getElementById("w-condition").innerText = "Errore di connessione";
            }
        }
    </script>
</body>
</html>
"""

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("[+] File public/index.html creato con successo!")

if __name__ == "__main__":
    main()
