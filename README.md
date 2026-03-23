# StarVisibility

Software desktop per la pianificazione di target astronomici per osservazioni dal sito **OGS/Teide Observatory**.  
Progettato per la campagna **CaNaPy – Aprile 2026** (2–12 Aprile 2026), ma completamente configurabile per qualsiasi campagna osservativa.

---

## Funzionalità principali

- Pianificazione automatica dei target per ogni slot temporale e settore del cielo
- Supporto a cataloghi online (VizieR/Hipparcos) e locali (CSV, FITS)
- Quattro settori configurabili (Nord, Sud, Est, Ovest) con vincoli indipendenti
- Bin di magnitudine configurabili (NGS_BRIGHT, NGS_MEDIUM, NGS_FAINT, LPC)
- Hotspot di puntamento con bonus di ranking (settore Sud, EL=70°, AZ=170°)
- Regola del "rising" per il settore Est (soglia di elevazione rilassata per stelle in ascesa)
- Export dei risultati in CSV (compatibile Excel) e XLSX opzionale
- Interfaccia grafica PySide6 con tema scuro
- Modalità headless (riga di comando) per integrazione in pipeline
- Cache locale del catalogo Hipparcos per operazioni offline

---

## Requisiti di sistema

- Python ≥ 3.11
- macOS, Linux o Windows
- Connessione internet (solo per la prima query VizieR; poi si usa la cache locale)

---

## Installazione

```bash
# 1. Clona o scarica il repository
cd "Software StarVisibility"

# 2. Crea un ambiente virtuale (consigliato)
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate.bat     # Windows

# 3. Installa le dipendenze
pip install -r requirements.txt
```

> **Nota**: `openpyxl` è necessario solo per l'export XLSX. Se non necessario, può essere omesso senza compromettere le funzionalità CSV.

---

## Utilizzo

### Interfaccia grafica

```bash
python app.py
```

All'avvio viene caricata automaticamente la configurazione predefinita per la campagna CaNaPy Aprile 2026. È possibile:

1. Modificare i parametri nella scheda **Setup** (date, orari, catalogo, bin di magnitudine)
2. Configurare i settori del cielo nella scheda **Settori**
3. Avviare la pianificazione con il pulsante **▶ Avvia Pianificazione**
4. Visualizzare i risultati nella scheda **Risultati**
5. Esportare i file dalla scheda **Export**

### Modalità headless (riga di comando)

```bash
# Con configurazione predefinita
python app.py --headless

# Con configurazione personalizzata
python app.py --headless --config percorso/mia_config.json

# Specificando la cartella di output
python app.py --headless --config mia_config.json --output-dir /percorso/output
```

---

## Creare un eseguibile Windows (EXE)

Per distribuire l'app senza richiedere Python installato, puoi generare un `.exe` con **PyInstaller**.

Da **PowerShell**, nella root del progetto:

```powershell
# EXE GUI (consigliato)
./build_exe.ps1 -Clean

# EXE con console (utile per usare --headless e vedere progresso su stdout)
./build_exe.ps1 -Console -Clean
```

Output:
- `dist/StarVisibility.exe` (GUI)
- `dist/StarVisibility-Console.exe` (console)

Nota: in versione EXE le cartelle runtime `.cache/`, `logs/`, `output/` vengono create **accanto all'eseguibile**.

---

## Creare un installer Windows

Per distribuire l'app con un classico wizard di installazione (scorciatoia nel Menu Start, disinstallatore, ecc.), usa il flag `-Installer`:

```powershell
# Compila entrambi gli EXE + genera l'installer in un solo comando
./build_exe.ps1 -Installer -Clean
```

Prerequisiti:
- **Inno Setup 6** — installalo con `winget install --id JRSoftware.InnoSetup`  
  (oppure scaricalo da [jrsoftware.org](https://jrsoftware.org/isinfo.php))

Output: `dist/StarVisibility-Setup-1.0.0.exe`

Il wizard di installazione:
- Installa in `C:\Program Files\StarVisibility\` (o `AppData` se non si ha l'accesso admin)
- Crea scorciatoie nel Menu Start (+ opzionale sul Desktop)
- Registra il disinstallatore tramite "Aggiungi/Rimuovi programmi"
- Include entrambi gli eseguibili, la configurazione default e il README

---

## Gestione della configurazione

La configurazione dell'applicazione è salvata in formato JSON. Dalla GUI:

- **File → Salva configurazione**: salva la configurazione corrente in un file `.json`
- **File → Carica configurazione**: carica una configurazione precedentemente salvata
- **File → Ripristina predefiniti**: ripristina la configurazione CaNaPy Aprile 2026

Il file `canopy_april2026_default.json` nella root del progetto contiene la configurazione predefinita della campagna.

---

## Struttura del progetto

```
Software StarVisibility/
├── app.py                          # Entry point (GUI e headless)
├── requirements.txt                # Dipendenze Python
├── canopy_april2026_default.json   # Config predefinita CaNaPy
├── README.md
│
├── src/
│   ├── models/
│   │   └── domain.py               # Dataclass del dominio
│   ├── config/
│   │   ├── settings.py             # Costanti e pesi di ranking
│   │   └── defaults.py             # Config predefinita CaNaPy Aprile 2026
│   ├── utils/
│   │   ├── datetime_utils.py       # Conversioni UTC/locale, finestre notturne
│   │   ├── validation.py           # Validazione input GUI
│   │   └── logging_utils.py        # Logging su file, console e GUI
│   ├── astro/
│   │   ├── observer.py             # EarthLocation dell'osservatorio
│   │   ├── coordinate_transform.py # Transform ICRS → AltAz vettorizzato
│   │   ├── visibility.py           # Controllo visibilità batch
│   │   ├── magnitude_bins.py       # Assegnazione stelle ai bin
│   │   └── catalog_service.py      # Adapter VizieR + catalogo locale
│   ├── core/
│   │   ├── sectors.py              # Utilità settori
│   │   ├── timeslots.py            # Generatore di TimeSlot
│   │   ├── constraints.py          # Predicati di vincolo
│   │   ├── ranking.py              # Funzione di scoring
│   │   ├── selector.py             # Selezione target per slot/settore
│   │   ├── scheduler.py            # Loop principale (notti × slot × settori)
│   │   └── planner.py              # Orchestratore top-level
│   ├── io/
│   │   ├── csv_exporter.py         # Export CSV (UTF-8 BOM)
│   │   ├── excel_formatter.py      # Export XLSX con openpyxl
│   │   └── persistence.py          # Salvataggio/caricamento JSON
│   └── gui/
│       ├── main_window.py          # Finestra principale
│       └── widgets/
│           ├── constraints_panel.py # Setup osservazione + bin magnitudine
│           ├── sector_editor.py     # Editor dei 4 settori
│           ├── results_table.py     # Tabella risultati ordinabile/filtrabile
│           ├── export_panel.py      # Pulsanti di export
│           └── log_panel.py         # Pannello log a colori
│
├── tests/
│   ├── test_sectors.py             # Test geometria settori
│   ├── test_timeslots.py           # Test generazione slot temporali
│   ├── test_constraints.py         # Test predicati di vincolo
│   └── test_selection.py           # Test ranking e selezione target
│
├── .cache/                         # Cache catalogo (auto-generata)
│   └── hipparcos_vmag7.5_cache.csv
├── output/                         # File di output (auto-generata)
│   ├── targets_YYYYMMDD_HHMMSS.csv
│   └── summary_YYYYMMDD_HHMMSS.csv
└── logs/                           # Log applicazione (auto-generata)
    └── starvisibility.log
```

---

## Osservatorio Teide (OGS)

| Parametro        | Valore                  |
|------------------|-------------------------|
| Latitudine       | 28.2994° N              |
| Longitudine      | 16.5097° W              |
| Altitudine       | 2390 m s.l.m.           |
| Fuso orario      | Europe/Madrid (UTC+1)   |
| Sito             | Tenerife, Isole Canarie |

---

## Configurazione CaNaPy Aprile 2026 (default)

### Campagna
- **Date**: 2–12 Aprile 2026
- **Notti osservative**: 10 notti
- **Slot per notte**: 2 ore ciascuno (inizio/fine notte astronomica)
- **Campionamento**: ogni 10 minuti per notte
- **Limite magnitudine catalogo**: V ≤ 7.5

### Settori del cielo

| Settore | AZ min | AZ max | EL min | EL max | Note |
|---------|--------|--------|--------|--------|------|
| Nord    | 315°   | 45°    | 30°    | 85°    | Avvolge attorno a 0° (Nord celeste) |
| Sud     | 135°   | 225°   | 30°    | 85°    | Hotspot EL=70°, AZ=170° |
| Est     | 45°    | 135°   | 30°    | 85°    | Rising rule: accetta stelle in salita ≥55° |
| Ovest   | 225°   | 315°   | 30°    | 85°    | Standard |

### Bin di magnitudine

| Nome       | V mag min | V mag max | Max target per slot |
|------------|-----------|-----------|----------------------|
| NGS_BRIGHT | (nessuno) | 2.0       | 2                    |
| NGS_MEDIUM | 2.0       | 4.0       | 3                    |
| NGS_FAINT  | 4.0       | 6.0       | 4                    |
| LPC        | 5.0       | 7.0       | 3                    |

> **Nota**: stelle con 5 < V < 6 soddisfano sia NGS_FAINT sia LPC. Il software le assegna al primo bin applicabile nell'ordine configurato.

---

## Ipotesi scientifiche

### Convenzione degli azimut
L'azimut segue la convenzione astronomica standard (FITS/astropy):
- **Nord = 0°**, Est = 90°, Sud = 180°, Ovest = 270°
- La misurazione è in senso orario guardando verso il basso (polo nord)

### Settore Nord — avvolgimento attorno a 0°
Il settore Nord ha `az_min = 315°` e `az_max = 45°`. Poiché `az_min > az_max`, il campo `wraps_zero = True` viene impostato automaticamente.  
La verifica di appartenenza usa la logica:
```
az >= az_min  OR  az <= az_max
```

### Controllo visibilità
Per ogni stella, vengono campionati N punti temporali equidistanti all'interno dello slot (inclusi il primo e l'ultimo minuto).  
Una stella è considerata **visibile** solo se **tutti** i campioni soddisfano simultaneamente:
- `el >= el_min` (soglia elevazione del settore)
- `el <= el_max`
- l'azimut del target rientra nel settore

### Regola del "rising" per il settore Est
Se un settore ha `rising_el_min` configurato (default: 55° per il settore Est), le stelle che si trovano in fase ascendente (`alt_fine > alt_inizio`) vengono accettate con la soglia rilassata `rising_el_min` invece di `el_min`.  
Questo permette di acquisire target interessanti appena sopra l'orizzonte est agli inizi della notte.

### Hotspot Sud
Il settore Sud ha un hotspot di puntamento preferenziale a EL=70°, AZ=170°.  
La funzione di scoring aggiunge un bonus che decresce esponenzialmente con la distanza angolare dall'hotspot (bonus massimo: 100 punti).

### Funzione di scoring
Il ranking combina:
1. **+1000** bonus se la stella è visibile per l'intero slot (tutti i campioni)
2. **+alt_media × 1.0** — premia elevazioni più alte (meno turbolenza)
3. **−dist_az × 0.3** — penalizza stelle lontane dal centro del settore
4. **+hotspot_bonus** — bonus esponenziale verso l'hotspot (solo se configurato)
5. **−80** penalità se la stella è stata selezionata nello slot precedente (promuove la rotazione)

### Riutilizzo delle stelle
Per default, una stella **non può essere selezionata due volte** nello stesso slot temporale e settore. In slot successivi, può essere ri-selezionata ma riceve una penalità di ranking (-80 punti) per favorire la diversità.

---

## Formato del catalogo locale

Se si usa un catalogo locale invece di VizieR, il file CSV o FITS deve contenere almeno le seguenti colonne (i nomi vengono riconosciuti in modo flessibile):

| Colonna richiesta | Alias accettati                          |
|-------------------|------------------------------------------|
| RA (gradi)        | `ra_deg`, `ra`, `RA`, `RAJ2000`          |
| Dec (gradi)       | `dec_deg`, `dec`, `Dec`, `DEJ2000`       |
| Magnitudine V     | `vmag`, `Vmag`, `Hpmag`, `V`, `mag`      |
| Nome (opz.)       | `name`, `Name`, `HIP`, `id`              |

Esempio di file CSV locale valido:
```csv
ra_deg,dec_deg,vmag,name
83.8221,−5.3911,0.45,Rigel
114.8255,5.2278,1.58,Procyon
```

---

## File di output

### `output/targets_YYYYMMDD_HHMMSS.csv`
Un record per ogni target selezionato, ordinato per notte → slot → settore → bin.

Colonne principali:

| Colonna              | Descrizione                                          |
|----------------------|------------------------------------------------------|
| `night_date`         | Data della notte (YYYY-MM-DD)                        |
| `slot_label`         | Etichetta slot (es. `Slot 1`)                        |
| `slot_start_utc`     | Inizio slot in UTC                                   |
| `slot_end_utc`       | Fine slot in UTC                                     |
| `sector_name`        | Nome settore (Nord, Sud, Est, Ovest)                 |
| `magnitude_bin`      | Nome bin magnitudine                                 |
| `star_id`            | Identificatore stella (es. HIP 12345)               |
| `star_name`          | Nome comune (se disponibile)                         |
| `ra_deg`             | Ascensione Retta (J2000, gradi)                      |
| `dec_deg`            | Declinazione (J2000, gradi)                          |
| `vmag`               | Magnitudine V                                        |
| `alt_mean_deg`       | Elevazione media durante lo slot                     |
| `alt_min_deg`        | Elevazione minima durante lo slot                    |
| `az_mean_deg`        | Azimut medio durante lo slot                         |
| `fully_visible`      | YES se visibile per tutto lo slot, NO altrimenti     |
| `is_repeat`          | YES se già selezionato nello slot precedente         |
| `ranking_score`      | Punteggio di ranking calcolato                       |

### `output/summary_YYYYMMDD_HHMMSS.csv`
Un record per ogni combinazione notte–slot–settore con statistica di copertura per bin.

---

## Esecuzione dei test

```bash
# Tutti i test
pytest tests/ -v

# Solo un file di test
pytest tests/test_sectors.py -v

# Con report di copertura (richiede pytest-cov)
pip install pytest-cov
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Cache del catalogo

Al primo avvio, il software scarica le stelle Hipparcos (catalogo VizieR `I/239/hip_main`) con V ≤ 7.5 e le salva in:

```
.cache/hipparcos_vmag7.5_cache.csv
```

Le esecuzioni successive useranno la cache locale. Per forzare il rinnovo della cache:
- GUI: nel pannello Setup, selezionare "Forza aggiornamento catalogo"
- Headless: eliminare manualmente il file `.cache/hipparcos_vmag7.5_cache.csv`

---

## Dipendenze

| Pacchetto     | Versione minima | Scopo                                     |
|---------------|-----------------|-------------------------------------------|
| astropy       | ≥ 6.0.0         | Coordinate astronomiche, AltAz, SkyCoord  |
| astroplan     | ≥ 0.10.0        | Pianificazione osservativa                |
| astroquery    | ≥ 0.4.7         | Query VizieR                              |
| numpy         | ≥ 1.26.0        | Calcolo vettorizzato                      |
| pandas        | ≥ 2.2.0         | Gestione catalogo e dati tabulari         |
| PySide6       | ≥ 6.7.0         | Interfaccia grafica                       |
| openpyxl      | ≥ 3.1.0         | Export XLSX (opzionale)                   |
| pytest        | ≥ 8.0.0         | Framework di test                         |
| pytest-qt     | ≥ 4.4.0         | Test GUI con PySide6                      |
| tzdata        | ≥ 2024.1        | Database fusi orari (zoneinfo)            |

---

## Autore e contesto

Sviluppato per la campagna **CaNaPy** (Canary Islands Natural Guide Star Survey),  
Osservatorio OGS – Teide, Tenerife, Isole Canarie.  
Instituto Nazionale di Astrofisica (INAF).

---

## Licenza

Uso interno INAF. Tutti i diritti riservati.
