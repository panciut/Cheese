# Pipeline Captioning — Indice dei Report di Fase

**Progetto**: AI4FQC — Project 07 GRANA_Captioning
**Data**: 2026-05-06
**Scope**: ricostruzione fase per fase del processo che ha portato dai dati grezzi al dataset finale `data/final/captions_final.csv` (38.437 righe).

Ogni fase ha un report dedicato che documenta: input/output, script coinvolto, cosa fa la fase, scelte tecniche con motivazione, alternative scartate, problemi evitati, statistiche.

## Fasi

| # | Fase | Script | Report |
|---:|---|---|---|
| 0 | Costruzione tabella unificata immagine ↔ commento | `build_dataset.py` | [00_unified_dataset.md](01_unified_dataset.md) |
| 1 | Preparazione caption deterministica | `prepare_captions.py` | [01_prepare_captions.md](02_prepare_captions.md) |
| 2 | Costruzione vocabolario controllato | `build_vocabulary.py` | [02_build_vocabulary.md](03_build_vocabulary.md) |
| 3 | Audit del vocabolario | `audit_vocabulary.py` | [03_audit_vocabulary.md](04_audit_vocabulary.md) |
| 4 | Pulizia caption + qualitatizzazione Spessore | `clean_captions.py` | [04_clean_captions.md](05_clean_captions.md) |
| 5 | Drop conservativo del rumore | `find_useless_captions.py` + `drop_useless_captions.py` | [05_drop_useless.md](06_drop_useless.md) |
| 6 | Design prompt LLM | `rewrite_prompt.py` + `render_prompts_for_review.py` | [06_prompt_design.md](07_prompt_design.md) |
| 7 | Pilot run | `pilot_rewrite.py` | [07_pilot_run.md](08_pilot_run.md) |
| 8 | Batch run completo | `rewrite_batch.py` | [08_batch_run.md](09_batch_run.md) |
| 9 | Salvage manuale dei NON_DESCRITTO | `manual_salvage.py` | [09_manual_salvage.md](10_manual_salvage.md) |
| 10 | Broadcast finale + sentence form + deliverables | `broadcast_captions.py` + `make_sentence_form.py` + `build_final_outputs.py` | [10_final_outputs.md](11_final_outputs.md) |

## Schema comune dei report

Ogni file segue questa struttura:

1. **Metadati** (script, input, output)
2. **Cosa fa la fase** (azioni concrete in ordine)
3. **Scelte chiave e motivazione** (tabella decisione/perché/alternativa scartata)
4. **Problemi evitati** (lista narrata)
5. **Statistiche output** (numeri concreti)

## Costo totale LLM della pipeline

| Step | Cost |
|---|---:|
| Pilot (105 caption, sync) | ~$0,20 |
| Aroma + Spessore batch parziale | ~$0,87 |
| Full batch (7.689 caption) | ~$4,50 |
| Manual salvage | $0 |
| Sentence form + polish | $0 |
| **Totale** | **~$5,60** |

Per confronto: Sonnet 4.6 sarebbe costato ~$13,50, Opus 4.7 ~$67.

## Output finale del processo

- **38.437 righe** training (image, panelist, attribute, caption, caption_sentence)
- **1.497 immagini uniche** coperte
- **7 attributi sensoriali** (Profumo, Aroma, Sapore, Texture, Spessore della Crosta, Struttura della Pasta, Colore della Pasta)
- **6.840 caption uniche** (compact form)
- **6.834 caption uniche** (sentence form)
- **0 numeri residui** in caption finale
- **0 unità di misura residue** (mm/cm/%)
- **2,1% drop rate** finale come `NON_DESCRITTO`
