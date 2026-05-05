"""Manual salvage of NON_DESCRITTO captions.

For each (attribute, caption_pre) pair where the LLM emitted
NON_DESCRITTO but the source actually contains a sensory descriptor,
provide a hand-crafted cleaned caption. Captions not listed here
remain as NON_DESCRITTO.

Apply to the existing rewrites_<attribute>.csv files in place; also
regenerate the side-by-side review_<attribute>.txt files.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path("/Users/marcopanciera/vsworkspace/Cheese/data")

# ---------------------------------------------------------------------------
# Manual salvage map.
# Entries written by hand after reviewing data/non_descritto_salvage.txt.
# Captions absent from this map keep the LLM's NON_DESCRITTO tag.
# ---------------------------------------------------------------------------
SALVAGE: dict[str, dict[str, str]] = {
    "Profumo": {
        "Difettato? Odori strani...": "Profumo difettoso e strano.",
        "chiuso": "Profumo chiuso.",
        "Molto elegante": "Profumo molto elegante.",
        "Profumo anomalo alla prima occasione fa diminuire i voto": "Profumo anomalo all'apertura.",
        "Solo all'apertura poi no l'ho sento": "Profumo percepibile solo all'apertura.",
        "leggermente difettoso": "Profumo leggermente difettoso.",
        "Sento poco. Non so se perché raffreddato o perché povero il fromage": "Profumo poco percepibile.",
        "Intensità messa negativa perché non piacevole, puzza,,,,": "Profumo sgradevole con puzza.",
        "non tipico da altro formaggio cotto": "Profumo non tipico, di altro formaggio cotto.",
        "dicreto buono in 3 pezzi su 4, ma in 1 c'è del marcio, putrido": "Profumo marcio e putrido in alcune porzioni.",
        "Strano. A tratti sentiva di pesce. Perplesso": "Profumo strano, di pesce a tratti.",
        "Prima olfazione non gradita. La definisco nostrano": "Profumo nostrano.",
        "Peccato per sfumatura bruciata!": "Profumo con sfumatura bruciata.",
        "non percettibile. senza odore": "Profumo impercettibile, senza odore.",
        "non percesco particolari odori": "Profumo poco percepibile.",
        "marcio, putrido,": "Profumo marcio e putrido.",
        "leggermente odore anomalo che non riconsoco": "Profumo leggermente anomalo.",
        "equilibrato, piacevole": "Profumo equilibrato e piacevole.",
        "Il sentore di nostrano é un dubbio": "Profumo con sentore di nostrano.",
        "Complesso e piacevole": "Profumo complesso e piacevole.",
        "solvente ___(": "Profumo di solvente.",
        "difettoso": "Profumo difettoso.",
        "Troppo debole per valutare con sicurezza": "Profumo molto debole.",
        "Troppa crosta": "Profumo con prevalenza di crosta.",
        "Putrido, trremendo": "Profumo putrido.",
        "Proprio aggressivo non piacevole": "Profumo aggressivo.",
        "Polvere anche,,,": "Profumo di polvere.",
        "Poco intenso manca tra i commenti?": "Profumo poco intenso.",
        "Non sa di grana": "Profumo non tipico del grana.",
        "Non equilibrato nell' espressione": "Profumo non equilibrato.",
        "Crosta solo accennata": "Profumo con leggero accenno di crosta.",
        "solo spezzando i pezzi e al momento della frattura si avverte puzza di marcio putrido, che x lo più se ne va asciugamdosi": "Profumo di marcio e putrido alla frattura, attenuato all'asciugatura.",
        "note poco tipiche e caratteristiche": "Profumo poco tipico.",
    },
    "Aroma": {
        "A proposito della fessure aggiungo : grasso, intuisco e abbasso di mezzo punto il voto": "Aroma grasso.",
        "difettoso": "Aroma difettoso.",
        "Sangue,,,": "Aroma di sangue.",
        "Il voto inerente a stalla sono stati due momenti e poi sparisce subito, per il salato ne manca un poco’": "Aroma di stalla momentaneo.",
        "ricorda un formaggio per; non tipico da grana": "Aroma non tipico del grana, ricorda un altro formaggio.",
        "nota lattea non sentita all-olfatto": "Aroma con assenza di nota lattea.",
        "Piuttosto anonimo rispetto al naso...": "Aroma piuttosto anonimo.",
        "Formaggio non grana... Ma non so dare definizione esatta": "Aroma non tipico del grana.",
        "povero rispetto a lnaso": "Aroma povero.",
        "note amare e": "Aroma con note amare.",
        "legge crosta": "Aroma di leggera crosta.",
        "Più povero che all' olfatto": "Aroma povero.",
        "mi torna una puzza non definita": "Aroma con puzza indefinita.",
        "formaggio rimasto in frigo troppo tempo": "Aroma di formaggio invecchiato.",
        "formaggio erborinato,": "Aroma di formaggio erborinato.",
        "Sangue…": "Aroma di sangue.",
        "Passato…": "Aroma di passato.",
        "Particolare sensibilità mia al fermentato": "Aroma fermentato.",
        "Manca di carattere": "Aroma povero di carattere.",
        "Immangiabile Fermentazione da Clostridium sporogenes": "Aroma di fermentazione da Clostridium sporogenes.",
        "Anonimo": "Aroma anonimo.",
    },
    "Sapore": {
        "Nostrano": "Sapore nostrano.",
        "Grasso": "Sapore grasso.",
        "Anonimo però!": "Sapore anonimo.",
        "Non grana": "Sapore non tipico del grana.",
        "crosta di formaggio": "Sapore di crosta di formaggio.",
        "Non da grana di 18 20 mesi": "Sapore non tipico di un grana stagionato.",
        "Nonostante la percezione di descrittori positivi e negativi lo valuto nel complesso positivo perché non vere ricettività ma caratteristiche attese in un formaggio stagionato": "Sapore tipico di formaggio stagionato.",
        "Non sgradevole, ma non lo riconosco come grana. troppo forti odori e consistenze": "Sapore non tipico del grana.",
        "crosta, formaggio cotto": "Sapore di crosta e formaggio cotto.",
        "Molto leggere le sensazioni segnate sul sapore": "Sapore molto leggero.",
        "formaggio cotto": "Sapore di formaggio cotto.",
        "equilibrio tra le diverse nte": "Sapore equilibrato.",
        "crosta, sa di vecchio": "Sapore di crosta e vecchio.",
        "crosta di formaggio, pane tostato": "Sapore di crosta di formaggio e pane tostato.",
        "anonimo con amaro...": "Sapore anonimo con amaro.",
        "Tanto umano, troppo": "Sapore molto umami.",
        "Sapore di nostrano": "Sapore nostrano.",
        "Il sapore anomalo. Atipico del grana": "Sapore anomalo, atipico del grana.",
        "Equilibrio travi gusti": "Sapore equilibrato tra i gusti.",
        "Anonimo è debole": "Sapore anonimo e debole.",
        "Anonimo poco intenso": "Sapore anonimo, poco intenso.",
        "Anonimo come sapore, poco espresso con...": "Sapore anonimo, poco espresso.",
        "panna": "Sapore di panna.",
        "molto cotto": "Sapore molto cotto.",
        "cotto": "Sapore di cotto.",
        "Poco carattere": "Sapore poco caratterizzato.",
        "Poco Miami,": "Sapore poco umami.",
        "Piatto": "Sapore piatto.",
        "Non sa da grana": "Sapore non tipico del grana.",
        "Non male, ma poco caratteristico": "Sapore poco caratteristico.",
        "Non da grana": "Sapore non tipico del grana.",
        "Leggermente Miami!!": "Sapore leggermente umami.",
        "Ambivalenza dove:-amaro...": "Sapore amaro.",
        "scarso in tutto": "Sapore scarso.",
    },
    "Texture": {
        "Strano!": "Texture strana.",
        "Astringente": "Texture astringente.",
        "Ho segnato durezza positiva perché ritengo abbia una bella espressione,": "Texture dura.",
        "Strana consistenza": "Texture dalla consistenza strana.",
        "Fastidioso in bocca": "Texture fastidiosa in bocca.",
        "Consistenza strana": "Texture dalla consistenza strana.",
        "pochissima tirosina, a": "Texture con pochissima tirosina.",
    },
    "Spessore della Crosta": {
        "Colore Sottocrosta grigiastro": "Crosta con sottocrosta grigiastra.",
        "Chiaro": "Crosta dal colore chiaro.",
        "Colore di fondo carico": "Crosta con colore di fondo carico.",
        "Colore tenue della crosta": "Crosta dal colore tenue.",
        "Pulita": "Crosta pulita.",
        "Nella norma": "Crosta nella norma.",
        "Un sottopiatto tende al verde": "Crosta con sottopiatto tendente al verde.",
        "Colore sfumato su base scura difficile vedere dove finisce": "Crosta dal colore sfumato su base scura.",
        "Colore di fondo carico contrasta meno il colore dello spessore": "Crosta con colore di fondo carico, poco contrastante.",
        "Poco contrasto dato l'ok colore di fondo carico": "Crosta con colore di fondo carico e poco contrasto.",
        "Microocchiatura, occhio, disidratazione, colore quasi verde sotto un piatto": "Crosta dal colore quasi verde sotto un piatto.",
        "Colore sotto crosta grigio da un lato rossastra dall'altro": "Crosta con sottocrosta grigia da un lato e rossastra dall'altro.",
        "Poco contrasto dato il colore di fondo molto carico": "Crosta con colore di fondo molto carico, poco contrasto.",
        "Intenso, difetto che dall'esterno entra nellunghia": "Crosta con difetto che dall'esterno entra nell'unghia.",
        "Colore sottocrosta grigiastro su sfondo molto carico": "Crosta con sottocrosta grigiastra su sfondo molto carico.",
        "Colore sottocrosta diverso da tutto il resto, rosellino": "Crosta con sottocrosta di colore diverso, rosellino.",
        "Colore sottocrosta di colore diverso tra piatti": "Crosta con sottocrosta di colore diverso tra piatti.",
        "Colore rossastra da un lato e grigio dall'altro": "Crosta con colore rossastro da un lato e grigio dall'altro.",
        "Colore pasta molto carico lo stacco tra crosta e pasta si vede poco": "Crosta con stacco poco visibile dalla pasta.",
        "Colore che sfuma su base di colore molto carico": "Crosta con colore sfumato su base molto carica.",
        "Colore sottocrosta sganciato sfuma verso linterno": "Crosta con sottocrosta sfumata verso l'interno.",
        "Un sottocrosta tendente al verde": "Crosta con sottocrosta tendente al verde.",
        "Sotto scalzo zona disidratata e ammuffita": "Crosta con scalzo disidratato e ammuffito.",
        "Evidente parte nera": "Crosta con evidente parte nera.",
        "Colori diversi fra i piatti": "Crosta di colori diversi tra i piatti.",
        "Colore sottocrosta molto sfumato": "Crosta con sottocrosta molto sfumata.",
        "Colore sottocrosta aranciato": "Crosta con sottocrosta aranciata.",
        "Colore sfondo molto carico": "Crosta con sfondo molto carico.",
        "Colore rosato sottocrosta": "Crosta con sottocrosta rosata.",
        "Colore rosa sottocrosta": "Crosta con sottocrosta rosa.",
        "Colore fondo carico": "Crosta con colore di fondo carico.",
        "Colore di fondo scuro": "Crosta con colore di fondo scuro.",
        "Colore carico solo su un piatto": "Crosta con colore carico solo su un piatto.",
        "Colore aranciato molto carico": "Crosta dal colore aranciato molto carico.",
        "Colore Sottocrosta sfumato": "Crosta con sottocrosta sfumata.",
        "Sottocrosta rosa": "Crosta con sottocrosta rosa.",
        "Modellatura nel sotto crosta": "Crosta con modellatura nel sottocrosta.",
        "Colori diversi": "Crosta di colori diversi.",
        "Colore grigiastro": "Crosta dal colore grigiastro.",
        "12 km più netta su 1 piatto": "Crosta più netta su un piatto.",
        "Molto chiaro": "Crosta molto chiara.",
        "Colore moltosfumato": "Crosta dal colore molto sfumato.",
        "Chiara": "Crosta chiara.",
        "Piatti senza crosta": "Crosta assente sui piatti.",
        "Superiore ai 14 km, sempre": "Crosta spessa.",
        "Intorno ai 10 km": "Crosta mediamente spessa.",
    },
    "Struttura della Pasta": {
        "Grassa...": "Pasta grassa.",
        "Peccato per occhi ...": "Pasta con occhi visibili.",
        "Leggera impugnatura in zona centrale": "Pasta con leggera impugnatura in zona centrale.",
        "1 punto in meno per lo spacco enorme. Una forma così Non dovrebbe arrivare al panel": "Pasta con spacco enorme.",
        "Strana anomalia tipo tara/muffa su uno scalzo": "Pasta con anomalia di muffa sullo scalzo.",
        "Nel commento sottoscala disidratato intendo disidratazione però più nei piatti": "Pasta con disidratazione più presente nei piatti.",
        "macchie rosa": "Pasta con macchie rosa.",
        "Voto positivo non considerando una vistosa spaccatura": "Pasta con vistosa spaccatura.",
        "Tipo sbrinz": "Pasta tipo sbrinz.",
        "Tantissimi punti di tirosina": "Pasta con tantissimi punti di tirosina.",
        "Struttura \"GRASSA": "Pasta grassa.",
        "Presenza di ossidazione interna": "Pasta con ossidazione interna.",
        "In un angolo sembra molto più umida": "Pasta più umida in un angolo.",
        "pastoso": "Pasta pastosa.",
        "Umido": "Pasta umida.",
        "Struttura non riuscita": "Pasta con struttura non riuscita.",
        "Sporca bruciata in parte": "Pasta sporca e in parte bruciata.",
        "Sbrinz": "Pasta tipo sbrinz.",
        "Non considero lo spacco": "Pasta con spacco.",
        "Muffa sotto scalzo": "Pasta con muffa sotto lo scalzo.",
        "Molto umida": "Pasta molto umida.",
        "Macchie": "Pasta con macchie.",
        "Macchia bianca come fosse muffa": "Pasta con macchia bianca simile a muffa.",
        "Difettosa": "Pasta difettosa.",
    },
    "Colore della Pasta": {
        "Voto basso per colpa della frattura con evidente colore rosa, altrimenti voto alto": "Pasta con frattura di colore rosa.",
        "Presenza di una potenziale macchia al centro NON CONSIDERATA NEL VOTO perché nascosta dal taglio a coltello": "Pasta con potenziale macchia al centro.",
        "Immatricolata conferisce quasi un colore rosato, ma solo pochi cm dopo la crosta. L'amore è spostato verso uno dei due piatti": "Pasta con leggero colore rosato vicino alla crosta.",
        "Non ho tenuto conto della macchia dovuta ad una \"correzione\" dello scalzo Se va considerato il difetto il voto è 5,0": "Pasta con macchia presente sullo scalzo.",
        "Presenza di ingresso di muffa laterale": "Pasta con muffa laterale.",
        "Grossa macchia di muffa": "Pasta con grossa macchia di muffa.",
        "Diversa fra i piatti": "Pasta di colore diverso tra i piatti.",
        "Disidratata solo da una parte": "Pasta disidratata in una parte.",
        "Regolare": "Pasta di colore regolare.",
        "In corrispondenza dell'occhio con siero": "Pasta con siero in corrispondenza degli occhi.",
        "Gessato": "Pasta dal colore gessato.",
        "Ad aree...": "Pasta a colori distribuiti per aree.",
        "Difetto so": "Pasta di colore difettoso.",
    },
}


# ---------------------------------------------------------------------------

def main() -> None:
    files = {
        "Profumo": "rewrites_Profumo.csv",
        "Aroma": "rewrites_Aroma.csv",
        "Sapore": "rewrites_Sapore.csv",
        "Texture": "rewrites_Texture.csv",
        "Spessore della Crosta": "rewrites_Spessore_della_Crosta.csv",
        "Struttura della Pasta": "rewrites_Struttura_della_Pasta.csv",
        "Colore della Pasta": "rewrites_Colore_della_Pasta.csv",
    }

    summary: list[tuple[str, int, int, int]] = []
    for attr, fname in files.items():
        path = ROOT / fname
        rows = list(csv.DictReader(path.open()))
        cols = list(rows[0].keys()) if rows else []
        attr_map = SALVAGE.get(attr, {})

        n_salvaged = 0
        n_unmatched: list[str] = []
        salvageable_keys_seen: set[str] = set()
        for r in rows:
            if r["caption_clean"] != "NON_DESCRITTO":
                continue
            key = r["caption_pre"]
            if key in attr_map:
                r["caption_clean"] = attr_map[key]
                n_salvaged += 1
                salvageable_keys_seen.add(key)

        # Detect map entries that didn't match any row (typo / drift)
        unused = [k for k in attr_map if k not in salvageable_keys_seen]

        # Write back
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow(r)

        # Regenerate review file
        review_path = ROOT / f"review_{fname.replace('rewrites_','').replace('.csv','.txt')}"
        # We need to know batch_id and model — read from existing review header
        rows.sort(key=lambda r: -int(r["frequency"]))
        lines = [
            f"## {attr}",
            f"unique captions: {len(rows)}",
            f"model: claude-haiku-4-5  (with manual salvage pass)",
            "",
            "(sorted by descending broadcast frequency)",
            "",
        ]
        for r in rows:
            suffix = f"   [{r.get('error','')}]" if r.get("error") else ""
            lines.append(f"  freq={r['frequency']:>4s}  raw : {r['caption_pre']}")
            lines.append(f"             clean: {r['caption_clean']}{suffix}")
        review_path.write_text("\n".join(lines) + "\n")

        summary.append((attr, n_salvaged, len(attr_map), len(unused)))
        if unused:
            print(f"warning: {attr} — {len(unused)} salvage entries didn't match any caption:")
            for u in unused:
                print(f"    {u!r}")

    print()
    print(f'{"attribute":26s} {"salvaged":>9s} {"map_size":>9s} {"unused":>7s}')
    print("-" * 60)
    total_s = total_m = 0
    for attr, salv, ms, un in summary:
        print(f"{attr:26s} {salv:9d} {ms:9d} {un:7d}")
        total_s += salv
        total_m += ms
    print("-" * 60)
    print(f'{"total":26s} {total_s:9d} {total_m:9d}')


if __name__ == "__main__":
    main()
