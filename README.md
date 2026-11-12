# Forma / 3DConverter

MVP locale per ricostruire prodotti ceramici **assialsimmetrici** a partire da profili SVG selezionati esplicitamente. Nessuna ricostruzione automatica da immagini, quote o più viste.

## Scelta dello stack

Il repository iniziale conteneva solo questo README, senza codice o convenzioni applicative. Backend **Python 3.11+ / FastAPI**, **CadQuery 2.8 / OpenCascade** per un vero BRep e STEP; Shapely per i controlli sezionali; svgpathtools per tracciati e Bézier; trimesh per verificare gli STL esportati. Frontend **JavaScript / Vite / Three.js**, senza framework UI o servizi esterni. I disegni restano nel browser e nelle richieste al server locale; non vengono archiviati dal backend.

## Installazione e avvio

Richiesti Python 3.11+, Node 20.19+ (consigliato 22) e npm. Linux necessita delle librerie runtime OpenGL/X11 anche se il backend non renderizza: su Debian/Ubuntu `sudo apt-get install libgl1 libglu1-mesa libxrender1 libxext6`. Usare un ambiente con wheel CadQuery/OCP disponibili (x86_64 Linux consigliato).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Aprire **http://localhost:8000** (oppure l'URL della preview). Riavviare il backend dopo la prima build: i file statici vengono montati se `web/dist` esiste all'avvio.

Per sviluppo: backend come sopra, poi in un secondo terminale `npm run dev`. Aprire la porta Vite indicata (normalmente 5173). Le richieste `/api` sono relative e inoltrate da Vite al backend; nessun indirizzo localhost è incorporato nel codice del browser.

## Prova rapida

1. Cliccare **Apri un esempio** oppure caricare `examples/vase.svg`.
2. Se si carica il file manualmente: esterno `esterno · #0`, interno `interno · #1`, asse verticale **X = 30**, unità **mm**, scala **1** mm per unità SVG, spessore minimo **2** mm. Non selezionare il terzo tracciato, che rappresenta l'asse.
3. Costruire: contenitore cilindrico aperto in alto, diametro **100 mm**, altezza **160 mm**, parete e fondo **6 mm**. Ruotare trascinando, zoomare con la rotellina; il pulsante ⤢ ripristina la vista.
4. Esportare STL o STEP; salvare il progetto JSON per conservare SVG originale, selezioni, correzioni, scala e parametri. Riaprendo il JSON il CAD viene ricostruito su richiesta, non memorizzato come risultato opaco.

Altri esempi sintetici, non riservati:
- `solid.svg`: esterno #0, asse 30, scala 1, confermare **oggetto pieno**.
- `curves.svg`: esterno #0, interno #1, asse 30, scala 1; pareti Bézier.
- `wrong-scale.svg`: provare scala 0.01, minimo 2 mm: controllo spessore fallisce. Non è possibile riconoscere una scala errata senza un riferimento reale.
- `invalid.svg`: #0 come esterno e oggetto pieno; profilo non monotono, costruzione bloccata.

## Contratto geometrico e modifica

- Selezionare **un mezzo profilo esterno aperto**, dal fondo al bordo (l'ordine inverso è accettato), alla destra di un asse verticale X costante. Se il disegno contiene più viste, scegliere i relativi tracciati; separare prima le viste che condividono un singolo tracciato connesso.
- Per i cavi selezionare separatamente l'interno, fondo → bordo. Il bordo interno ed esterno devono avere la stessa altezza (tolleranza 0.01 mm); il fondo interno deve stare sopra quello esterno e il suo raggio deve essere positivo.
- La sezione è chiusa **esplicitamente** collegando i bordi in alto, il fondo interno all'asse e l'asse al fondo esterno. Senza interno non si inventano cavità o offset: serve confermare un oggetto pieno. Lo spessore è un **vincolo**, non un generatore di pareti.
- Per correggere un contorno aprire “Correggi un profilo”, scegliere Esterno o Interno, trascinare i punti nell'anteprima oppure modificare l'elenco di coppie `[x,y]` in coordinate SVG e applicarlo. Cliccare un tracciato lo assegna al ruolo attualmente scelto per la correzione. L'asse si modifica numericamente.
- Scala sempre esplicita: unità fisiche per unità SVG, senza assumere che pixel o attributi `width`/`height` siano quote. “Calibra con una quota nota” divide la misura reale per la distanza corrispondente nel disegno, che va misurata/verificata dall'utente. Unità: mm, cm, pollici; CAD ed esportazioni in mm. STL è un formato senza unità, configurare mm nello slicer.
- Il ritiro è **disattivo** inizialmente e non ha percentuale precompilata. Quando richiesto: `dimensione modello = dimensione finale desiderata / (1 - ritiro/100)`. È una compensazione lineare isotropa, non una simulazione di cottura. Anteprima ed esportazioni usano lo stesso fattore. Il vincolo di spessore è verificato sulla geometria finale desiderata, prima della compensazione.

## Formati, precisione e limiti

**SVG principale**: `path` (linee, Bézier quadratiche/cubiche, archi), `line`, `polyline`, `polygon` come candidati selezionabili. Sottotracciati disconnessi separati. Massimo 1 MB, 150 candidati, 2000 punti per profilo / 20000 complessivi. Non vengono eseguiti script né inserito l'SVG originale nel DOM. Testi, immagini e riferimenti `use` non diventano geometria; `defs`, maschere e clipping sono esclusi. Trasformazioni rifiutate: applicarle/appiattirle nell'editor prima di importare. Non sono risolti CSS, clipping, istanze, visibilità e unità annidate: esportare tracciati semplici in un unico sistema di coordinate. Quote/assi/linee nascoste non sono riconosciuti semanticamente: **la selezione corretta è responsabilità dell'utente**, mai automatica.

**PDF non importato direttamente**: convertire prima il PDF vettoriale in SVG con un editor dedicato, controllare unità, trasformazioni e contorni. Un PDF scansionato non contiene profili precisi: occorre ricalco e verifica esplicita della scala e dei bordi. Gli SVG con sole immagini vengono rifiutati. Un raster incorporato insieme a tracciati viene segnalato e ignorato, non misurato.

**Curve**: campionamento di 48 intervalli per segmento curvo, seguito da spline CAD interpolate per ogni segmento, mantenendo gli spigoli tra segmenti. Le rette restano rette. Se si cambia il numero dei punti corretti si usa una spline complessiva per un profilo originariamente curvo. Non è una conversione analitica esatta Bézier → NURBS e non esiste ancora una tolleranza adattiva certificata: verificare la fedeltà prima di prototipare. Auto-intersezioni e spessore minimo sono verificati sulla sezione **campionata** (distanza minima euclidea fra profili e spessore del fondo), non con analisi globale di spessore sul BRep.

**Geometrie ammesse**: altezza monotona dal fondo al bordo, senza rientri in altezza, più cavità, manici, decorazioni, fori laterali o forme non di rivoluzione. Un contorno chiuso completo non è un mezzo profilo valido e viene normalmente respinto dal controllo di monotonia. I profili aperti non conformi al contratto, auto-intersecanti, degeneri, sovrapposti, sul lato errato dell'asse o troppo sottili sono bloccati con errori. Non si ricuciono automaticamente disegni spezzati e non si deducono parti mancanti.

Prima dell'anteprima e di ogni export si verifica un singolo solido OpenCascade valido e con volume positivo. **STL**: tessellazione a tolleranza 0.08 mm / angolare 0.15 rad, rilettura e controllo mesh chiusa e orientata con volume. **STEP**: rilettura e controllo di validità/singolo solido. Le dimensioni del modello mostrate provengono dal bounding box CAD; quelle finali desiderate dal profilo campionato. I controlli non costituiscono certificazione metrologica o di producibilità.

## Architettura e test

- `app/importer.py`: importazione SVG → candidati senza interpretazione semantica.
- `app/interpretation.py`: contratto assialsimmetrico, parametri versionabili, controlli della sezione e compensazione.
- `app/cad.py`: costruzione BRep di rivoluzione e tessellazione per il viewer.
- `app/main.py`: API importazione, costruzione, export verificati e file statici.
- `web/src.js`: flusso UI, correzione 2D, Three.js e persistenza JSON lato client.

```bash
source .venv/bin/activate
python -m pytest -q
npm run build
```

I test coprono esempi validi pieni/cavi/curvi, dimensioni e volume analitici, unità/scala, ritiro, profili non validi, importazione non sicura/non supportata, salvataggio parametri e round-trip STL/STEP. La build controlla il frontend; non c'è ancora una suite browser end-to-end.

La separazione tra candidati vettoriali, interpretazione e CAD permette di aggiungere in futuro altri interpreti di ricostruzione, senza promettere che più viste eliminino le ambiguità. Applicazione locale per un singolo operatore: nessuna autenticazione, isolamento di processo CAD, code job, undo o archivio server; il lock serializza i lavori CAD. Per esposizione pubblica servono autenticazione, timeout e limiti risorse in processi isolati. La validazione dell'input non sostituisce questi requisiti.
