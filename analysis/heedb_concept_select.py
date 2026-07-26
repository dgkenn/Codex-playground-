#!/usr/bin/env python3
"""Resolve OMOP concept ids for life-support procedures and goals-of-care observations.

WHY THIS EXISTS. `procedure_source_value` in this database holds numeric BILLING CODES -- "36415" is a
venipuncture, "99214" an office visit -- so a text regex over the source value matches nothing and the
extraction returns an empty file. That empty file is dangerous precisely because it looks like a clean
negative. The names live in the OMOP `concept` vocabulary and must be joined through `procedure_concept_id`.

This resolves a concept-id set and PRINTS EVERY NAME IT MATCHED, in frequency order, so the set is inspected
before anything is extracted with it. An instrument built from an unverified code list is an instrument nobody
can defend, and this project has already retracted one analysis whose instrument turned out to be measuring the
charting system rather than the clinic.

Usage:
    python analysis/heedb_concept_select.py procedure   -> /tmp/eeg_probe/concept_ids_procedure.txt
    python analysis/heedb_concept_select.py observation -> /tmp/eeg_probe/concept_ids_observation.txt
"""
import csv, os, re, sys

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OUTDIR = os.environ.get("CONCEPT_OUT", "/tmp/eeg_probe")

# Deliberately WIDE patterns. The set is printed for inspection and narrowed by reading it, rather than
# guessed narrowly up front and silently missing the term this database happens to use.
PATTERNS = {
    "procedure": re.compile(
        r"extubat|weaning from ventilat|ventilator wean|discontinu\w* .*ventilat|"
        r"mechanical ventilat|invasive ventilat|artificial respirat|respiratory ventilat|"
        r"insertion of endotracheal|endotracheal intubat|\bintubation\b|tracheostom|"
        r"cardiopulmonary resuscitat|resuscitation|extracorporeal membrane|"
        r"withdraw\w* of (life|treatment|care)|withdrawal of life|terminal wean|"
        r"comfort care|comfort measures|palliative care|hospice care|"
        r"do not resuscitat|allow natural death", re.I),
    "observation": re.compile(
        r"\bDNR\b|do not resuscitat|\bDNI\b|do not intubat|code status|full code|"
        r"resuscitation status|goals of care|comfort measures|comfort care|palliative|hospice|"
        r"allow natural death|\bPOLST\b|\bMOLST\b|advance directive|"
        r"limitation of (treatment|care)|withdraw\w* of (life|treatment|care)", re.I),
}
# Which OMOP domain each selection is allowed to draw from. Without this a "palliative care" CONDITION concept
# would be pulled into a procedure filter and match nothing in procedure_occurrence.
DOMAINS = {"procedure": {"procedure", "device"}, "observation": {"observation", "measurement", "condition"}}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PATTERNS:
        print(f"usage: {sys.argv[0]} {{{'|'.join(PATTERNS)}}}")
        return 64
    kind = sys.argv[1]
    rx, doms = PATTERNS[kind], DOMAINS[kind]

    path = f"{OMOP}/concept.csv"
    if not os.path.exists(path):
        print(f"missing {path} -- run: python analysis/heedb_omop_extract.py concept")
        return 1

    hits, n, bydom = [], 0, {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            n += 1
            nm = (r.get("concept_name") or "").strip()
            dom = (r.get("domain_id") or "").strip().lower()
            if not nm or dom not in doms or not rx.search(nm):
                continue
            try:
                cid = int(r["concept_id"])
            except Exception:
                continue
            hits.append((cid, nm, dom, (r.get("vocabulary_id") or "").strip(),
                         (r.get("standard_concept") or "").strip()))
            bydom[dom] = bydom.get(dom, 0) + 1
    print(f"scanned {n:,} concepts; matched {len(hits):,} in domains {sorted(doms)}")
    for d, c in sorted(bydom.items(), key=lambda x: -x[1]):
        print(f"   domain {d:12s} {c:6,d}")

    seen, uniq = set(), []
    for cid, nm, dom, voc, std in hits:
        if cid not in seen:
            seen.add(cid); uniq.append((cid, nm, dom, voc, std))
    print(f"\nEVERY MATCHED NAME (inspect before using; {len(uniq):,} unique concept ids):")
    for cid, nm, dom, voc, std in sorted(uniq, key=lambda x: x[1].lower())[:400]:
        print(f"   {cid:>10d}  {voc:10s} {dom:10s} {'S' if std == 'S' else ' '}  {nm[:88]}")
    if len(uniq) > 400:
        print(f"   ... {len(uniq)-400:,} more not shown")

    out = f"{OUTDIR}/concept_ids_{kind}.txt"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(out, "w") as fh:
        fh.write("\n".join(str(c) for c, _, _, _, _ in uniq))
    # Also write id -> name, because the extracted procedure rows carry only the numeric concept id and the
    # analysis has to tell an extubation from a tracheostomy from a comfort-care order.
    namep = f"{OUTDIR}/concept_names_{kind}.csv"
    with open(namep, "w", newline="") as fh:
        wr = csv.writer(fh); wr.writerow(["concept_id", "concept_name", "domain_id", "vocabulary_id"])
        for cid, nm, dom, voc, _ in uniq:
            wr.writerow([cid, nm, dom, voc])
    print(f"\nwrote {len(uniq):,} concept ids -> {out}")
    print(f"wrote id->name map -> {namep}")
    print("Use with:  ID_FILTER_COL=<procedure|observation>_concept_id ID_FILTER_FILE=" + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
