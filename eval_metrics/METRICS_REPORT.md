# Report sulle metriche di valutazione — Captioning Trentingrana

Questo documento spiega in dettaglio le metriche usate per valutare i modelli
di captioning, **cosa misura ciascuna**, **come si legge il suo valore**, e
**cosa significano i numeri ottenuti** sul dataset Trentingrana. È pensato per
essere letto anche da chi non conosce le metriche di NLG (Natural Language
Generation).

Tutti i numeri citati provengono da `eval_metrics/metrics_summary.csv`,
calcolato su 43 file di predizioni (4 baseline + 3 modelli addestrati, su 7
attributi per-attributo + 3 versioni "global").

---

## 0. Perché non basta BLEU

Il problema di fondo del captioning: **esistono molti modi corretti di
descrivere la stessa immagine**. Il dataset ha **un solo riferimento** per
immagine (la frase scritta da un panelista). Una metrica che confronta parola
per parola punisce le riformulazioni corrette.

Esempio reale dal dataset:

| | Testo |
|---|---|
| Riferimento (panelista) | *"Il formaggio ha pasta compatta con occhiatura rada."* |
| Predizione del modello | *"Il formaggio ha pasta dura con piccola occhiatura."* |

Stesso significato, parole diverse. BLEU-4 ≈ 0.1 (quasi nessuna sequenza di 4
parole in comune), ma la descrizione è **corretta**. Per questo affianchiamo a
BLEU sei metriche complementari, ognuna che guarda un aspetto diverso.

Le metriche si dividono in due famiglie:

- **Basate sul testo** (confrontano predizione ↔ riferimento testuale):
  BLEU, METEOR, ROUGE-L, CIDEr, BERTScore.
- **Basate sull'immagine** (confrontano predizione ↔ immagine, ignorano il
  riferimento): CLIPScore.
- **Specifica del dominio**: Conformità Vocabolario.

---

## 1. BLEU-1 e BLEU-4

### Cosa misura
La **precisione degli n-gram**: quante sequenze di *n* parole consecutive della
predizione compaiono anche nel riferimento.
- **BLEU-1** → singole parole (1-gram). Misura *"ho usato le parole giuste?"*
- **BLEU-4** → sequenze di 4 parole. Misura *"ho usato la fraseologia giusta,
  nell'ordine giusto?"* È molto più severa.

### Range e lettura
Valore in **[0, 1]**, più alto è meglio.
- BLEU-4 **> 0.4** → ottimo per questo dominio (frasi brevi e formulaiche).
- BLEU-4 **0.2–0.4** → discreto.
- BLEU-4 **< 0.15** → il modello non riproduce la struttura del riferimento.

### Cosa dicono i nostri numeri
- Modelli per-attributo: BLEU-4 ≈ **0.30–0.45**. Buono, perché le caption del
  dominio sono brevi e ripetitive (*"Il formaggio ha un aroma di…"*).
- Modelli **global**: BLEU-4 ≈ **0.13**. Crollo netto: un modello unico per
  tutti gli attributi è molto più debole di sette modelli specializzati.
- Baseline **most_frequent**: BLEU-1 **0.84–0.90**, il più alto di tutti!

### Il tranello di BLEU (importante)
`most_frequent` emette **sempre la stessa identica caption** (la più frequente
nel training) e ottiene il BLEU-1 più alto in assoluto. Questo **non** significa
che sia il modello migliore: significa che il prefisso costante *"Il formaggio
ha un…"* combacia quasi sempre, gonfiando il punteggio. **BLEU premia la
ripetizione del template, non la comprensione.** È il motivo per cui servono le
altre metriche.

---

## 2. METEOR

### Cosa misura
Come BLEU-1, ma **più indulgente e linguisticamente consapevole**: prima di
confrontare, allinea le parole usando **stemming** (radici: *"compatto"* ≈
*"compatta"*) e **sinonimi**. Bilancia precisione e recall (penalizza sia il
dire troppo che il dire troppo poco).

### Range e lettura
Valore in **[0, 1]**, più alto è meglio. Tende a essere **più alto di BLEU-4**
sullo stesso testo, perché perdona le variazioni morfologiche.
- METEOR **> 0.6** → forte sovrapposizione di contenuto.
- METEOR **0.4–0.6** → contenuto parzialmente allineato.
- METEOR **< 0.35** → contenuto divergente.

### Cosa dicono i nostri numeri
- Modelli per-attributo: METEOR ≈ **0.53–0.66**. Coerente: catturano il
  contenuto anche quando cambiano la forma.
- Modelli **global**: ≈ **0.29**. Stesso crollo visto con BLEU.

METEOR e BLEU raccontano qui la **stessa storia** (per-attributo buono, global
debole), il che è un buon segnale di robustezza: non sono in contraddizione.

---

## 3. ROUGE-L

### Cosa misura
La **Longest Common Subsequence (LCS)**: la più lunga sequenza di parole che
appare in **entrambe** le frasi nello stesso ordine, ma **non necessariamente
consecutive**. Premia chi rispetta l'ordine generale degli elementi senza
richiedere combaciamento esatto contiguo.

Esempio: *"pasta compatta con occhiatura rada"* vs *"pasta molto compatta con
occhiatura"* → LCS = *"pasta compatta con occhiatura"* (4 parole, in ordine).

### Range e lettura
Valore in **[0, 1]**, più alto è meglio. Tipicamente tra BLEU-4 e METEOR.
- ROUGE-L **> 0.6** → buona struttura condivisa.
- ROUGE-L **< 0.35** → poca sovrapposizione ordinata.

### Cosa dicono i nostri numeri
Modelli per-attributo: ≈ **0.50–0.67**; global ≈ **0.30**. Si muove sempre in
tandem con METEOR/BLEU — conferma la coerenza del quadro.

---

## 4. CIDEr

### Cosa misura
È la metrica progettata **apposta per il captioning**. Come BLEU usa gli n-gram
(da 1 a 4), ma li **pesa con TF-IDF**: gli n-gram **rari e informativi** valgono
molto, quelli comuni quasi nulla.

- Parole come *"occhiatura"*, *"piccante"*, *"erborinato"* → rare nel corpus →
  **peso alto**.
- Parole come *"il"*, *"ha"*, *"formaggio"* → ovunque → **peso ≈ 0**.

In pratica risponde a: *"il modello azzecca i termini sensoriali **salienti**,
o riempie con parole generiche?"*

> Nota implementativa: usiamo un'implementazione standalone (CIDEr-D
> semplificato) con **un solo riferimento** per immagine. È quindi una stima
> consistente per confrontare i modelli **tra loro**, non un valore confrontabile
> con benchmark esterni a riferimenti multipli (es. COCO, dove i valori arrivano
> a ~1–10 grazie a 5 riferimenti).

### Range e lettura
Valore **≥ 0**, senza tetto fisso (qui scala ×10). Più alto è meglio.
**Va letto in relazione, non in assoluto.** Quello che conta è il **confronto
tra modelli sullo stesso attributo**.
- Sul nostro dataset: CIDEr **> 1.0** = ottimo allineamento dei termini chiave;
  **0.3–0.7** = medio; **< 0.2** = il modello usa parole generiche / sbagliate.

### Cosa dicono i nostri numeri (qui CIDEr aggiunge informazione vera)
CIDEr **separa i modelli dove BLEU-4 li appiattiva**. Esempio su **Spessore
della Crosta**:

| Modello | BLEU-4 | CIDEr |
|---|---|---|
| most_frequent | 0.44 | **2.29** |
| m6_vit_gpt | 0.42 | **1.76** |
| m1_cnn_lstm | 0.41 | **1.60** |
| m3_vit_transformer | 0.40 | **1.55** |
| freq_weighted | 0.39 | **1.04** |

BLEU-4 dice "tutti uguali" (0.39–0.44); CIDEr dice "c'è un ordine netto". E
conferma il finding: su attributi con una caption dominante (es. crosta spessa),
la baseline costante **most_frequent vince anche su CIDEr** (2.29) — perché il
riferimento *è* quasi sempre quella frase frequente.

Attenzione anche a **Struttura della Pasta** con most_frequent: BLEU-1 alto
(0.79) ma CIDEr basso (0.52) e METEOR il più basso (0.46) → la caption costante
è lunga e combacia poco sui termini rari. È il caso da manuale in cui BLEU-1
inganna e CIDEr smaschera.

---

## 5. BERTScore

### Cosa misura
La **similarità semantica** tra predizione e riferimento, calcolata con
**embedding contestuali** (un modello BERT, qui in italiano). Non guarda le
parole esatte: guarda se i **significati** combaciano nello spazio vettoriale.
Per ogni parola della predizione cerca la parola più simile nel riferimento e
viceversa (precision, recall, F1). Riportiamo l'**F1** (`bertscore_f`).

Risponde a: *"il modello ha capito il **concetto**, anche se usa sinonimi o una
costruzione diversa?"*

Esempio: *"crosta sottile e regolare"* vs *"rivestimento esterno fine e
uniforme"* → BLEU ≈ 0, ma BERTScore alto (significato identico).

### Range e lettura
Valore tipicamente in **[0.7, 1.0]** per l'italiano (lo "zero" pratico è alto,
perché due frasi qualsiasi in italiano condividono già struttura).
**Per questo va letto in modo relativo**, non assoluto:
- BERTScore-F **> 0.90** → forte equivalenza semantica.
- **0.84–0.90** → buona equivalenza.
- **< 0.83** → contenuto semanticamente più distante.

### Cosa dicono i nostri numeri (e perché qui è poco discriminante)
Tutti i valori stanno in **0.83–0.92**. Differenze piccole. Il motivo: **tutte
le frasi parlano di formaggio** con la stessa struttura (*"Il formaggio ha…"*),
quindi il BERT italiano le trova tutte semanticamente vicine. BERTScore è utile
come **sanity check** ("nessun modello produce frasi semanticamente assurde"),
ma per **classificare** i modelli CIDEr e CLIPScore discriminano meglio.

Unico segnale leggibile: i modelli **global** scendono a ≈ **0.80** (vs ≈ 0.87
per-attributo) — di nuovo il global è il più debole.

---

## 6. Conformità Vocabolario (metrica custom del progetto)

### Cosa misura
La **percentuale di parole** della caption generata che appartengono al
**vocabolario controllato** del progetto (`data/vocabulary/vocabulary.csv`, 1278
forme superficiali attestate dai panelisti esperti). Risponde a una domanda che
nessuna metrica standard pone: *"il modello «parla formaggio» con la
terminologia sensoriale certificata, o inventa termini propri?"*

Esempio:
- *"pasta compatta con occhiatura rada"* → tutti termini attestati → ~1.0
- *"texture densa con buchi piccoli"* → *texture*, *buchi* non attestati → ~0.5

È la metrica **più originale e specifica** del progetto: misura l'aderenza al
registro tecnico, cosa cruciale per un sistema che deve produrre descrizioni
sensoriali valide.

### Range e lettura
Valore in **[0, 1]**, più alto = più aderente al lessico controllato.
- **> 0.55** → forte uso del vocabolario di dominio.
- **0.45–0.55** → uso moderato (molte parole funzionali "il/ha/di" che non sono
  nel vocabolario abbassano fisiologicamente il valore).
- **< 0.45** → il modello si allontana dal registro.

> Nota: il vocabolario contiene solo lemmi **sensoriali**, non parole funzionali.
> Quindi anche una caption perfetta non raggiunge 1.0 (le "parole di servizio"
> contano come fuori-vocabolario). Va letto in modo **relativo tra modelli**.

### Cosa dicono i nostri numeri
- Valori ≈ **0.48–0.61** per i modelli addestrati.
- Attributi visivi e descrittivi (**Texture ≈ 0.60–0.67**, **Struttura ≈ 0.56**)
  hanno conformità più alta: usano più aggettivi sensoriali attestati.
- I modelli **global** hanno conformità **pari o superiore** ai per-attributo su
  diversi attributi (≈ 0.54), pur avendo BLEU/METEOR molto peggiori: producono
  frasi più "lessicalmente corrette" ma meno fedeli al riferimento specifico.

---

## 7. CLIPScore (la metrica più importante per il captioning)

### Cosa misura
È l'**unica** metrica che **guarda l'immagine**. Usa CLIP (un modello addestrato
su milioni di coppie immagine–testo, qui in versione **multilingue** per
l'italiano) per proiettare immagine e caption nello stesso spazio vettoriale, e
ne calcola la **similarità coseno**:

```
CLIPScore = cos( CLIP_immagine(fetta) , CLIP_testo(caption_predetta) )
```

**Ignora completamente il riferimento del panelista.** Risponde alla domanda più
onesta per un sistema di captioning: *"questa caption descrive bene
**questa immagine**, indipendentemente da cosa ha scritto il panelista?"*

È esattamente la metrica raccomandata come *"single most useful follow-up"* nei
documenti del progetto, perché aggira il problema del **riferimento singolo**.

> Nota implementativa: modello `xlm-roberta-base-ViT-B-32` (pesi LAION-5B).
> La colonna `image_path` è stata ricostruita agganciando ogni predizione alla
> riga del test-split corrispondente (per ordine, validato al 100% sui
> `caption_ref`). Usiamo la vista **fetta**.

### Range e lettura
Per CLIP multilingue, la coseno grezza è **bassa in valore assoluto**
(tipicamente **0.15–0.30** anche per coppie corrette). **Non va letto come una
percentuale**: 0.20 non significa "20% giusto". Conta:
1. il **confronto relativo** (tra attributi, tra modelli);
2. la **direzione**: più alto = caption più appropriata all'immagine.

Sul nostro setup:
- CLIPScore **≈ 0.20–0.21** → attributo ben descrivibile visivamente.
- CLIPScore **≈ 0.18** → attributo poco legato all'aspetto visivo.

### Cosa dicono i nostri numeri — DUE risultati chiave

**Risultato 1 — CLIPScore è quasi identico tra modelli e baseline.**
Media CLIPScore sui 7 attributi per-attributo:

| Modello | CLIPScore medio |
|---|---|
| most_frequent (caption **costante**) | 0.190 |
| freq_weighted | 0.192 |
| m1_cnn_lstm | 0.192 |
| m3_vit_transformer | 0.192 |
| m6_vit_gpt | 0.193 |

I modelli addestrati **non battono** una baseline che spara sempre la stessa
frase ignorando l'immagine (scarto max 0.003, dentro il rumore). **Interpretazione:**
con l'**encoder congelato**, i modelli non àncorano davvero la caption ai
contenuti visivi — fanno *language modeling* sulla distribuzione delle caption.
Questa è la **conferma indipendente** (e quantitativa) del risultato dello
*shuffle test* del report: se i modelli sfruttassero l'immagine, supererebbero la
baseline costante su CLIPScore. Non lo fanno.

**Risultato 2 — CLIPScore distingue attributi visibili da non visibili.**
La variazione vera è **per attributo**, non per modello:

| Attributo | CLIPScore ≈ | Osservabile dall'immagine? |
|---|---|---|
| Texture | 0.208 | ✅ sì (aspetto della pasta) |
| Colore della Pasta | 0.206 | ✅ sì |
| Struttura della Pasta | 0.198 | ✅ sì |
| Spessore della Crosta | 0.184 | ⚠️ visibile ma bordo piccolo |
| Profumo | 0.184 | ❌ olfatto |
| Sapore | 0.184 | ❌ gusto |
| Aroma | 0.181 | ❌ olfatto |

CLIP "vede" che gli attributi **visivi** (texture, colore, struttura) sono più
descrivibili dall'immagine, mentre **olfatto/gusto** (aroma, profumo, sapore)
restano bassi per chiunque — nessuna immagine può rivelare un sapore. È un
controllo di sanità che **valida** il comportamento di CLIPScore: si comporta
come ci aspetteremmo da una metrica image-grounded.

Eccezione istruttiva: **Spessore della Crosta** è fisicamente visibile ma ha
CLIPScore basso (0.184) — perché la crosta è una porzione piccola della fetta e
CLIP la pesa poco rispetto alla pasta che domina l'immagine.

---

## 8. Quadro d'insieme: quale metrica per quale domanda

| Domanda | Metrica da guardare |
|---|---|
| Riproduce la fraseologia esatta del riferimento? | BLEU-4 |
| Usa le parole giuste (anche flesse/sinonimi)? | METEOR |
| Rispetta l'ordine generale degli elementi? | ROUGE-L |
| Azzecca i termini sensoriali **salienti**? | **CIDEr** |
| Ha capito il **concetto** (anche riformulando)? | BERTScore |
| Parla con la **terminologia certificata** del dominio? | **Conformità Vocabolario** |
| La caption è **appropriata all'immagine**? | **CLIPScore** |

**Lettura combinata, tre casi tipici osservati nei dati:**

1. **Caption costante (`most_frequent`)** → BLEU-1 altissimo, ma CIDEr/METEOR
   incoerenti e CLIPScore = a tutti gli altri. *Diagnosi: gonfia BLEU senza
   capire nulla.* È la dimostrazione che BLEU da solo inganna.
2. **Modelli per-attributo (m1/m3/m6)** → buoni su tutte le metriche testuali,
   ma CLIPScore piatto rispetto alle baseline. *Diagnosi: bravi a modellare il
   linguaggio delle caption, deboli nell'usare l'immagine.*
3. **Modelli global** → tutte le metriche testuali crollano, CLIPScore invariato.
   *Diagnosi: un modello unico per 7 attributi non regge; meglio specializzare.*

---

## 9. Come riprodurre

Ambiente isolato in `eval_metrics/.venv` (non tocca le dipendenze del training).

```powershell
# 1. (una tantum) crea il venv e installa le dipendenze
.\eval_metrics\setup.ps1

# 2. (una tantum) aggiungi image_path ai predictions.csv (per CLIPScore)
.\eval_metrics\.venv\Scripts\python.exe eval_metrics\add_image_paths.py

# 3. calcola tutte le metriche su tutta la cartella predictions/
.\eval_metrics\.venv\Scripts\python.exe eval_metrics\compute_metrics.py predictions --images-root .

# Varianti utili:
#   --no-bertscore      salta BERTScore (niente download modello BERT)
#   --no-clipscore      salta CLIPScore (molto più veloce, solo metriche testuali)
#   --out path.csv      file di output del riepilogo
```

Output: tabella a video + `metrics_summary.csv` (43 righe × 8 metriche).

### Metriche implementate
| Metrica | Libreria / metodo | Riferimenti |
|---|---|---|
| BLEU-1/4, METEOR, ROUGE-L | HuggingFace `evaluate` | testuale, 1 ref |
| CIDEr | implementazione standalone (TF-IDF n-gram) | testuale, 1 ref |
| BERTScore-F | `bert-score`, `lang="it"` | semantica |
| Conformità Vocabolario | custom su `vocabulary.csv` | dominio |
| CLIPScore | `open_clip`, `xlm-roberta-base-ViT-B-32` (LAION-5B) | image-grounded |

---

## 10. Limiti e caveat onesti

- **Riferimento singolo**: tutte le metriche testuali confrontano contro **una**
  caption. CIDEr e BLEU ne soffrono strutturalmente; per questo CLIPScore (che
  ignora il riferimento) è il complemento più prezioso.
- **CIDEr** qui è una versione semplificata a 1 riferimento: confrontabile **tra
  i nostri modelli**, non con benchmark esterni.
- **BERTScore** è poco discriminante su questo dominio (frasi tutte simili).
- **CLIPScore** usa CLIP generico (non fine-tuned sul formaggio): coglie tratti
  visivi grossolani (colore, texture), non sfumature sensoriali fini. I valori
  assoluti bassi sono normali e non vanno letti come percentuali.
- **CLIPScore costante tra modelli** è esso stesso il risultato: indica che il
  collo di bottiglia è l'**encoder congelato**, non il decoder. Il prossimo
  esperimento naturale (già indicato nel report) è il **fine-tuning
  dell'encoder** e ri-misurare CLIPScore: se i modelli iniziano a staccarsi
  dalla baseline, è la prova che l'immagine viene finalmente sfruttata.
