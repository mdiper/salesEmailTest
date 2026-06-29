# SalesEmailTool

Sistema di gestione email con analisi automatica (sicurezza, paese, contenuto) e routing basato su regole configurabili.

---

## Prerequisiti

- **Python 3.12+** (testato con 3.14)
- **Node.js 18+** e npm
- **MySQL 8.0+** attivo e raggiungibile
- **Git**

---

## Setup iniziale (solo la prima volta)

### 1. Clona il repository

```bash
git clone https://github.com/mdiper/salesEmailTest.git
cd salesEmailTest
```

### 2. Crea e attiva il virtual environment Python

```bash
python -m venv venv
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Installa le dipendenze Python

```bash
pip install -r requirements.txt
```

### 4. Configura le variabili d'ambiente

Copia il file di esempio e compilalo con i tuoi dati:

```bash
cp .env.example .env
```

Modifica `.env` con i valori reali:

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=la_tua_password
DB_NAME=salesemailtool

# IMAP
IMAP_HOST=mail.tuoserver.it
IMAP_PORT=993
IMAP_USERNAME=email@dominio.it
IMAP_PASSWORD=password_email

# App
LOG_LEVEL=INFO
ATTACHMENTS_DIR=data/attachments
POLL_INTERVAL_SECONDS=60

# Auth API
JWT_SECRET=una-chiave-segreta-lunga-e-casuale
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

### 5. Inizializza il database

Assicurati che MySQL sia in esecuzione, poi:

```bash
python src/db/init_db.py
python src/db/seed_account.py
python src/db/seed_routing_rules.py
```

### 6. Installa le dipendenze frontend

```bash
cd frontend
npm install
cd ..
```

---

## Avvio della pipeline completa

Per far funzionare tutto il sistema servono **3 processi** (apri 3 terminali separati):

### Terminale 1: Pipeline di elaborazione email (IMAP polling)

Questo processo si connette alla casella email via IMAP, scarica le nuove email e le processa attraverso tutta la pipeline (sicurezza → paese → contenuto → routing).

```bash
.\venv\Scripts\Activate.ps1
python main.py
```

Vedrai i log delle email processate in tempo reale. Per fermare: `Ctrl+C`.

### Terminale 2: API Backend (FastAPI)

Questo processo avvia il server REST API sulla porta 8000.

```bash
.\venv\Scripts\Activate.ps1
python start_api.py
```

L'API sarà disponibile su `http://localhost:8000`.  
Documentazione interattiva (Swagger): `http://localhost:8000/docs`

### Terminale 3: Frontend React

```bash
cd frontend
npm run dev
```

Il frontend sarà disponibile su `http://localhost:5173`.

---

## Accesso al pannello web

1. Apri il browser su `http://localhost:5173`
2. Accedi con le credenziali configurate in `.env`:
   - Username: `admin`
   - Password: `admin123`

---

## Riepilogo comandi rapidi (copia-incolla)

Se hai già fatto il setup iniziale, per avviare tutto basta:

**Terminale 1 - Pipeline:**
```powershell
cd C:\Users\m.diperna\Desktop\Appunti-matteo\Progetti\SalesEmailTool
.\venv\Scripts\Activate.ps1
python main.py
```

**Terminale 2 - API:**
```powershell
cd C:\Users\m.diperna\Desktop\Appunti-matteo\Progetti\SalesEmailTool
.\venv\Scripts\Activate.ps1
python start_api.py
```

**Terminale 3 - Frontend:**
```powershell
cd C:\Users\m.diperna\Desktop\Appunti-matteo\Progetti\SalesEmailTool\frontend
npm run dev
```

---

## Endpoint API principali

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/health` | GET | Health check (nessuna auth) |
| `/api/auth/login` | POST | Login, restituisce JWT |
| `/api/auth/me` | GET | Info utente corrente |
| `/api/emails` | GET | Lista email (paginata, filtrabile) |
| `/api/emails/{id}` | GET | Dettaglio singola email |
| `/api/stats` | GET | Statistiche aggregate |
| `/api/routing-rules` | GET/POST | Lista e creazione regole |
| `/api/routing-rules/{id}` | GET/PUT/DELETE | CRUD singola regola |
| `/api/routing-rules/dry-run` | POST | Simulazione regole |

Tutti gli endpoint (tranne `/health` e `/api/auth/login`) richiedono header:
```
Authorization: Bearer <token_jwt>
```

---

## Test

### Test API (senza frontend):
```bash
.\venv\Scripts\Activate.ps1
python tests/test_api.py
```

### Test singoli moduli:
```bash
python tests/test_security_engine.py
python tests/test_country_detector.py
python tests/test_content_analyzer.py
python tests/test_routing_engine.py
python tests/test_pipeline.py
```

---

## Struttura del progetto

```
SalesEmailTool/
├── main.py                  # Entry point pipeline IMAP
├── start_api.py             # Entry point server API
├── requirements.txt         # Dipendenze Python
├── .env                     # Configurazione (non committare)
├── src/
│   ├── api/                 # FastAPI endpoints
│   │   ├── app.py           # App principale con CORS
│   │   ├── auth.py          # Autenticazione JWT
│   │   ├── emails.py        # Endpoint email
│   │   ├── stats.py         # Endpoint statistiche
│   │   └── routing_rules.py # CRUD regole routing
│   ├── ingestion/           # Client IMAP e parsing email
│   ├── security/            # Analisi sicurezza (header, phishing, malware)
│   ├── country/             # Rilevamento paese di origine
│   ├── content/             # Analisi contenuto (classificazione, summary, entities)
│   ├── routing/             # Motore regole e azioni
│   ├── pipeline.py          # Orchestratore pipeline completa
│   ├── db/                  # Connessione DB, repository, schema
│   └── utils/               # Config, logger
├── frontend/                # React app (Vite)
│   ├── src/
│   │   ├── pages/           # Login, Dashboard, EmailList, EmailDetail, Rules
│   │   ├── components/      # Layout, ProtectedRoute
│   │   ├── context/         # AuthContext
│   │   └── api/             # Client axios configurato
│   └── package.json
├── tests/                   # Script di test
└── config/                  # YARA rules e altre config
```

---

## Note

- La pipeline processa le email in ordine di arrivo, una alla volta
- Se un'email risulta **DANGEROUS** dalla security analysis, il sistema salta le analisi di paese e contenuto (fast-track) e applica direttamente le regole di routing
- Gli allegati non vengono scaricati per sicurezza: viene salvata solo la metadata (nome, tipo, dimensione, hash)
- Le credenziali di default (`admin`/`admin123`) vanno cambiate in produzione modificando `.env`
