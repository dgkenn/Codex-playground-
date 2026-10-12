"""mimic_severity_scores.py -- MULTI-SCORE severity adjustment of the MIMIC-IV
requirement -> mortality association (the 'signal vs just-sicker' question, hardened).

The headline reviewer attack on 'norepinephrine requirement predicts death (OR ~3.8/SD)'
is: the dose is just an ILLNESS-SEVERITY marker. mimic_mortality_severity.py answered it
against ONE crude proxy set (age, #vasopressors, distinct-ICD COUNT, ICU-LOS), and
mimic_sofa_lactate.py against first-24h lactate + SOFA labs. This module re-runs the
association against SEVERAL *standard, validated* comorbidity/severity scores so the
stability of the requirement OR can be read across specifications, not asserted from one:

  1. CHARLSON Comorbidity Index per hadm -- Quan 2005 ENHANCED ICD-9-CM + ICD-10 mapping
     (17 categories, standard integer weights), summed to a weighted Charlson score.
  2. ELIXHAUSER comorbidities per hadm -- AHRQ/Quan ICD-9-CM + ICD-10 mapping (31 groups),
     summed to the van Walraven (2009) weighted point score.
  3. LAB-SEVERITY block -- if cache/mimic_labs24h.csv exists (a labevents download was in
     progress at build time): log-transformed skewed labs + the SOFA lab components +
     lactate. Handled gracefully: absent -> comorbidity models run now; the lab + FULL
     models are clearly marked PENDING the labevents download.
  4. Per-stay requirement = median norepi rate (0 < rate <= 5 mcg/kg/min), merged
     stay -> hadm -> hospital_expire_flag, plus age, #vasopressors, Charlson, van Walraven.
  5. MULTI-MODEL requirement->mortality OR per SD (standardized logistic) under:
       (a) age only, (b) +Charlson, (c) +van Walraven, (d) +#vasopressors,
       (e) +lab-severity [if labs present], (f) FULL (all available).
     Each: OR + bootstrap 95% CI (resample stays) + DeltaAUC the requirement adds over
     that severity model. A STABILITY TABLE of the requirement OR across specifications.

VERDICT: is the requirement->mortality OR stable and >1 across ALL severity specifications
(signal beyond severity) or does it collapse under comorbidity/lab adjustment (mostly
severity)? Honest. NOTE: SOFA here is approximated by lab components + #vasopressors and
still lacks GCS + PaO2/FiO2 (those live only in the 30GB chartevents).

Reads MIMIC raw from $MIMIC_RAW. Reuses cache/mimic_norepi.csv (norepi segments) and
cache/mimic_vaso_count.csv (cardiovascular-SOFA proxy). stdlib only at import; numpy/sklearn
lazy. Writes cache/mimic_severity_scores.json + docs/MIMIC_SEVERITY_SCORES.md.
Run: python3 -m vitaldb_aki.analysis.mimic_severity_scores
"""
from __future__ import annotations
import csv as _csv
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628
MIMIC_RAW = os.environ.get("MIMIC_RAW",
    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad")
NOREPI_CSV = os.path.join(_CACHE, "mimic_norepi.csv")
VASO_CSV = os.path.join(_CACHE, "mimic_vaso_count.csv")
LABS_CSV = os.path.join(_CACHE, "mimic_labs24h.csv")
OUT_JSON = os.path.join(_CACHE, "mimic_severity_scores.json")

# Lab directionality / log-transform plan (mirrors mimic_sofa_lactate.LAB_SPEC).
_LAB_NAMES = ["lactate", "bilirubin", "creatinine", "platelets", "bun", "wbc",
              "bicarbonate", "inr", "albumin", "hemoglobin", "anion_gap", "sodium"]
_LAB_LOG = {"lactate", "bilirubin", "creatinine", "bun", "wbc", "inr"}   # right-skewed -> log

# ---------------------------------------------------------------------------
# Charlson Comorbidity Index -- Quan et al. 2005 (Med Care) ENHANCED ICD-9-CM
# + ICD-10 code mapping, 17 categories, standard integer weights.
# Patterns are matched against DOT-FREE codes (MIMIC stores e.g. "41401", "I2510")
# as PREFIXES, exactly as the Quan code lists enumerate them.
# ---------------------------------------------------------------------------
# Each category: (icd9_prefixes, icd10_prefixes, weight).
CHARLSON = {
    "myocardial_infarction": (
        ["410", "412"],
        ["I21", "I22", "I252"], 1),
    "congestive_heart_failure": (
        ["39891", "40201", "40211", "40291", "40401", "40403", "40411", "40413",
         "40491", "40493", "4254", "4255", "4256", "4257", "4258", "4259", "428"],
        ["I099", "I110", "I130", "I132", "I255", "I420", "I425", "I426", "I427",
         "I428", "I429", "I43", "I50", "P290"], 1),
    "peripheral_vascular_disease": (
        ["0930", "4373", "440", "441", "4431", "4432", "4433", "4434", "4435",
         "4436", "4437", "4438", "4439", "4471", "5571", "5579", "V434"],
        ["I70", "I71", "I731", "I738", "I739", "I771", "I790", "I792", "K551",
         "K558", "K559", "Z958", "Z959"], 1),
    "cerebrovascular_disease": (
        ["36234", "430", "431", "432", "433", "434", "435", "436", "437", "438"],
        ["G45", "G46", "H340", "I60", "I61", "I62", "I63", "I64", "I65", "I66",
         "I67", "I68", "I69"], 1),
    "dementia": (
        ["290", "2941", "3312"],
        ["F00", "F01", "F02", "F03", "F051", "G30", "G311"], 1),
    "chronic_pulmonary_disease": (
        ["4168", "4169", "490", "491", "492", "493", "494", "495", "496", "500",
         "501", "502", "503", "504", "505", "5064", "5081", "5088"],
        ["I278", "I279", "J40", "J41", "J42", "J43", "J44", "J45", "J46", "J47",
         "J60", "J61", "J62", "J63", "J64", "J65", "J66", "J67", "J684", "J701",
         "J703"], 1),
    "rheumatic_disease": (
        ["4465", "7100", "7101", "7102", "7103", "7104", "7140", "7141", "7142",
         "7148", "725"],
        ["M05", "M06", "M315", "M32", "M33", "M34", "M351", "M353", "M360"], 1),
    "peptic_ulcer_disease": (
        ["531", "532", "533", "534"],
        ["K25", "K26", "K27", "K28"], 1),
    "mild_liver_disease": (
        ["07022", "07023", "07032", "07033", "07044", "07054", "0706", "0709",
         "570", "571", "5733", "5734", "5738", "5739", "V427"],
        ["B18", "K700", "K701", "K702", "K703", "K709", "K713", "K714", "K715",
         "K717", "K73", "K74", "K760", "K762", "K763", "K764", "K768", "K769",
         "Z944"], 1),
    "diabetes_without_complication": (
        ["2500", "2501", "2502", "2503", "2508", "2509"],
        ["E100", "E101", "E106", "E108", "E109", "E110", "E111", "E116", "E118",
         "E119", "E120", "E121", "E126", "E128", "E129", "E130", "E131", "E136",
         "E138", "E139", "E140", "E141", "E146", "E148", "E149"], 1),
    "diabetes_with_complication": (
        ["2504", "2505", "2506", "2507"],
        ["E102", "E103", "E104", "E105", "E107", "E112", "E113", "E114", "E115",
         "E117", "E122", "E123", "E124", "E125", "E127", "E132", "E133", "E134",
         "E135", "E137", "E142", "E143", "E144", "E145", "E147"], 2),
    "hemiplegia_paraplegia": (
        ["3341", "342", "343", "3440", "3441", "3442", "3443", "3444", "3445",
         "3446", "3449"],
        ["G041", "G114", "G801", "G802", "G81", "G82", "G830", "G831", "G832",
         "G833", "G834", "G839"], 2),
    "renal_disease": (
        ["40301", "40311", "40391", "40402", "40403", "40412", "40413", "40492",
         "40493", "582", "5830", "5831", "5832", "5834", "5836", "5837", "585",
         "586", "5880", "V420", "V451", "V56"],
        ["I120", "I131", "N032", "N033", "N034", "N035", "N036", "N037", "N052",
         "N053", "N054", "N055", "N056", "N057", "N18", "N19", "N250", "Z490",
         "Z491", "Z492", "Z940", "Z992"], 2),
    "malignancy": (   # any malignancy incl leukemia/lymphoma (non-metastatic)
        ["140", "141", "142", "143", "144", "145", "146", "147", "148", "149",
         "150", "151", "152", "153", "154", "155", "156", "157", "158", "159",
         "160", "161", "162", "163", "164", "165", "166", "167", "168", "169",
         "170", "171", "172", "174", "175", "176", "179", "180", "181", "182",
         "183", "184", "185", "186", "187", "188", "189", "190", "191", "192",
         "193", "194", "195", "200", "201", "202", "203", "204", "205", "206",
         "207", "208", "2386"],
        ["C0", "C1", "C2", "C30", "C31", "C32", "C33", "C34", "C37", "C38", "C39",
         "C40", "C41", "C43", "C45", "C46", "C47", "C48", "C49", "C50", "C51",
         "C52", "C53", "C54", "C55", "C56", "C57", "C58", "C60", "C61", "C62",
         "C63", "C64", "C65", "C66", "C67", "C68", "C69", "C70", "C71", "C72",
         "C73", "C74", "C75", "C76", "C81", "C82", "C83", "C84", "C85", "C88",
         "C90", "C91", "C92", "C93", "C94", "C95", "C96", "C97"], 2),
    "moderate_severe_liver_disease": (
        ["4560", "4561", "4562", "5722", "5723", "5724", "5728"],
        ["I850", "I859", "I864", "I982", "K704", "K711", "K721", "K729", "K765",
         "K766", "K767"], 3),
    "metastatic_solid_tumor": (
        ["196", "197", "198", "199"],
        ["C77", "C78", "C79", "C80"], 6),
    "aids_hiv": (
        ["042", "043", "044"],
        ["B20", "B21", "B22", "B24"], 6),
}

# ---------------------------------------------------------------------------
# Elixhauser comorbidities -- Quan 2005 enhanced ICD-9-CM + ICD-10, with the
# van Walraven (2009) integer point weights per group (the validated single
# summary score). 31 groups. Same dot-free PREFIX matching.
# (icd9_prefixes, icd10_prefixes, vanWalraven_weight)
# ---------------------------------------------------------------------------
ELIX = {
    "chf": (["39891", "40201", "40211", "40291", "40401", "40403", "40411",
             "40413", "40491", "40493", "4254", "4255", "4256", "4257", "4258",
             "4259", "428"],
            ["I099", "I110", "I130", "I132", "I255", "I420", "I425", "I426",
             "I427", "I428", "I429", "I43", "I50", "P290"], 7),
    "arrhythmia": (["4260", "42613", "4267", "4269", "42610", "42612", "4270",
                    "4271", "4272", "4273", "4274", "4276", "4278", "4279", "7850",
                    "99601", "99604", "V450", "V533"],
                   ["I441", "I442", "I443", "I456", "I459", "I47", "I48", "I49",
                    "R000", "R001", "R008", "T821", "Z450", "Z950"], 5),
    "valvular_disease": (["0932", "394", "395", "396", "397", "424", "7463",
                          "7464", "7465", "7466", "V422", "V433"],
                         ["A520", "I05", "I06", "I07", "I08", "I091", "I098",
                          "I34", "I35", "I36", "I37", "I38", "I39", "Q230",
                          "Q231", "Q232", "Q233", "Z952", "Z953", "Z954"], -1),
    "pulm_circ": (["4150", "4151", "416", "4170", "4178", "4179"],
                  ["I26", "I27", "I280", "I288", "I289"], 4),
    "pvd": (["0930", "4373", "440", "441", "4431", "4432", "4433", "4434", "4435",
             "4436", "4437", "4438", "4439", "4471", "5571", "5579", "V434"],
            ["I70", "I71", "I731", "I738", "I739", "I771", "I790", "I792", "K551",
             "K558", "K559", "Z958", "Z959"], 2),
    "htn": (["401", "402", "403", "404", "405"],
            ["I10", "I11", "I12", "I13", "I15"], 0),
    "paralysis": (["3341", "342", "343", "3440", "3441", "3442", "3443", "3444",
                   "3445", "3446", "3449"],
                  ["G041", "G114", "G801", "G802", "G81", "G82", "G830", "G831",
                   "G832", "G833", "G834", "G839"], 7),
    "neuro_other": (["3319", "3320", "3321", "3334", "3335", "33392", "334", "335",
                     "3362", "340", "341", "345", "3481", "3483", "7803", "7843"],
                    ["G10", "G11", "G12", "G13", "G20", "G21", "G22", "G254",
                     "G255", "G312", "G318", "G319", "G32", "G35", "G36", "G37",
                     "G40", "G41", "G931", "G934", "R470", "R56"], 6),
    "chronic_pulm": (["4168", "4169", "490", "491", "492", "493", "494", "495",
                      "496", "500", "501", "502", "503", "504", "505", "5064",
                      "5081", "5088"],
                     ["I278", "I279", "J40", "J41", "J42", "J43", "J44", "J45",
                      "J46", "J47", "J60", "J61", "J62", "J63", "J64", "J65",
                      "J66", "J67", "J684", "J701", "J703"], 3),
    "diabetes_uncomp": (["2500", "2501", "2502", "2503"],
                        ["E100", "E101", "E109", "E110", "E111", "E119", "E120",
                         "E121", "E129", "E130", "E131", "E139", "E140", "E141",
                         "E149"], 0),
    "diabetes_comp": (["2504", "2505", "2506", "2507", "2508", "2509"],
                      ["E102", "E103", "E104", "E105", "E106", "E107", "E108",
                       "E112", "E113", "E114", "E115", "E116", "E117", "E118",
                       "E122", "E123", "E124", "E125", "E126", "E127", "E128",
                       "E132", "E133", "E134", "E135", "E136", "E137", "E138",
                       "E142", "E143", "E144", "E145", "E146", "E147", "E148"], 0),
    "hypothyroid": (["2409", "243", "244", "2461", "2468"],
                    ["E00", "E01", "E02", "E03", "E890"], 0),
    "renal_failure": (["40301", "40311", "40391", "40402", "40403", "40412",
                       "40413", "40492", "40493", "585", "586", "5880", "V420",
                       "V451", "V56"],
                      ["I120", "I131", "N18", "N19", "N250", "Z490", "Z491",
                       "Z492", "Z940", "Z992"], 5),
    "liver_disease": (["07022", "07023", "07032", "07033", "07044", "07054",
                       "0706", "0709", "456", "570", "571", "5722", "5723",
                       "5724", "5728", "5733", "5734", "5738", "5739", "V427"],
                      ["B18", "I85", "I864", "I982", "K70", "K711", "K713", "K714",
                       "K715", "K717", "K72", "K73", "K74", "K760", "K762", "K763",
                       "K764", "K765", "K766", "K767", "K768", "K769", "Z944"], 11),
    "pud": (["5317", "5319", "5327", "5329", "5337", "5339", "5347", "5349"],
            ["K257", "K259", "K267", "K269", "K277", "K279", "K287", "K289"], 0),
    "aids_hiv": (["042", "043", "044"],
                 ["B20", "B21", "B22", "B24"], 0),
    "lymphoma": (["200", "201", "202", "2030", "2386"],
                 ["C81", "C82", "C83", "C84", "C85", "C88", "C96", "C900",
                  "C902"], 9),
    "metastatic_cancer": (["196", "197", "198", "199"],
                          ["C77", "C78", "C79", "C80"], 12),
    "solid_tumor": (["140", "141", "142", "143", "144", "145", "146", "147",
                     "148", "149", "150", "151", "152", "153", "154", "155",
                     "156", "157", "158", "159", "160", "161", "162", "163",
                     "164", "165", "166", "167", "168", "169", "170", "171",
                     "172", "174", "175", "176", "179", "180", "181", "182",
                     "183", "184", "185", "186", "187", "188", "189", "190",
                     "191", "192", "193", "194", "195"],
                    ["C0", "C1", "C2", "C30", "C31", "C32", "C33", "C34", "C37",
                     "C38", "C39", "C40", "C41", "C43", "C45", "C46", "C47",
                     "C48", "C49", "C50", "C51", "C52", "C53", "C54", "C55",
                     "C56", "C57", "C58", "C60", "C61", "C62", "C63", "C64",
                     "C65", "C66", "C67", "C68", "C69", "C70", "C71", "C72",
                     "C73", "C74", "C75", "C76", "C97"], 4),
    "rheumatoid": (["4465", "7100", "7101", "7102", "7103", "7104", "7140",
                    "7141", "7142", "7148", "725"],
                   ["L940", "L941", "L943", "M05", "M06", "M08", "M120", "M123",
                    "M30", "M310", "M311", "M312", "M313", "M32", "M33", "M34",
                    "M35", "M45", "M461", "M468", "M469"], 0),
    "coagulopathy": (["286", "2871", "2873", "2874", "2875"],
                     ["D65", "D66", "D67", "D68", "D691", "D693", "D694", "D695",
                      "D696"], 3),
    "obesity": (["2780"],
                ["E66"], -4),
    "weight_loss": (["260", "261", "262", "263", "7832", "7994"],
                    ["E40", "E41", "E42", "E43", "E44", "E45", "E46", "R634",
                     "R64"], 6),
    "fluid_electrolyte": (["2536", "276"],
                          ["E222", "E86", "E87"], 5),
    "blood_loss_anemia": (["2800"],
                          ["D500"], -2),
    "deficiency_anemia": (["2801", "2808", "2809", "281"],
                          ["D508", "D509", "D51", "D52", "D53"], -2),
    "alcohol_abuse": (["2652", "2911", "2912", "2913", "2915", "2916", "2917",
                       "2918", "2919", "303", "3050", "3575", "4255", "5353",
                       "5710", "5711", "5712", "5713", "980", "V113"],
                      ["F10", "E52", "G621", "I426", "K292", "K700", "K703",
                       "K709", "T51", "Z502", "Z714", "Z721"], 0),
    "drug_abuse": (["292", "304", "3052", "3053", "3054", "3055", "3056", "3057",
                    "3058", "3059", "V6542"],
                   ["F11", "F12", "F13", "F14", "F15", "F16", "F18", "F19",
                    "Z715", "Z722"], -7),
    "psychoses": (["2938", "295", "29604", "29614", "29644", "29654", "297",
                   "298"],
                  ["F20", "F22", "F23", "F24", "F25", "F28", "F29", "F302",
                   "F312", "F315"], 0),
    "depression": (["2962", "2963", "2965", "3004", "309", "311"],
                   ["F204", "F313", "F314", "F315", "F32", "F33", "F341", "F412",
                    "F432"], -3),
}


def _norm(code):
    """Uppercase, strip whitespace/dots (MIMIC is already dot-free but be safe)."""
    return code.strip().upper().replace(".", "")


def _build_prefix_matcher(spec):
    """spec: {category: (icd9_prefixes, icd10_prefixes, weight)} ->
    (matcher9, matcher10) regex-free fast prefix lookup, returns weight dict per cat."""
    p9 = {cat: tuple(v[0]) for cat, v in spec.items()}
    p10 = {cat: tuple(v[1]) for cat, v in spec.items()}
    w = {cat: v[2] for cat, v in spec.items()}
    return p9, p10, w


def _categories_for(code, version, p9, p10):
    """Return set of categories matched by one (code, icd_version)."""
    code = _norm(code)
    pref = p9 if str(version) == "9" else p10
    out = set()
    for cat, prefixes in pref.items():
        for pfx in prefixes:
            if code.startswith(pfx):
                out.add(cat)
                break
    return out


def _comorbidity_scores():
    """Stream diagnoses_icd -> per-hadm Charlson categories + Elixhauser groups.
    Returns (charlson_score, charlson_cats, vanwalraven_score, elix_count) per hadm,
    plus a category-prevalence tally for the smoke test."""
    src = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    if not os.path.exists(src):
        raise FileNotFoundError(f"diagnoses_icd not found at {src}")
    c9, c10, cw = _build_prefix_matcher(CHARLSON)
    e9, e10, ew = _build_prefix_matcher(ELIX)
    hadm_charl = {}   # hadm -> set(charlson cats)
    hadm_elix = {}    # hadm -> set(elix groups)
    n = 0
    with gzip.open(src, "rt") as fh:
        for row in _csv.DictReader(fh):
            n += 1
            h = row.get("hadm_id")
            if not h:
                continue
            code, ver = row.get("icd_code", ""), row.get("icd_version", "")
            cc = _categories_for(code, ver, c9, c10)
            if cc:
                hadm_charl.setdefault(h, set()).update(cc)
            ec = _categories_for(code, ver, e9, e10)
            if ec:
                hadm_elix.setdefault(h, set()).update(ec)
    # Charlson hierarchy: if metastatic_solid_tumor present, don't double-count malignancy;
    # if diabetes_with_complication present, drop diabetes_without; if
    # moderate_severe_liver present, drop mild_liver. (Quan/Charlson standard.)
    def _resolve_charlson(cats):
        cats = set(cats)
        if "metastatic_solid_tumor" in cats:
            cats.discard("malignancy")
        if "diabetes_with_complication" in cats:
            cats.discard("diabetes_without_complication")
        if "moderate_severe_liver_disease" in cats:
            cats.discard("mild_liver_disease")
        return cats
    # Elixhauser hierarchy (van Walraven): collapse uncomplicated into complicated.
    def _resolve_elix(cats):
        cats = set(cats)
        if "diabetes_comp" in cats:
            cats.discard("diabetes_uncomp")
        if "metastatic_cancer" in cats:
            cats.discard("solid_tumor")
        return cats

    all_hadm = set(hadm_charl) | set(hadm_elix)
    charlson_score, charlson_cats = {}, {}
    vw_score, elix_count = {}, {}
    charl_tally = {k: 0 for k in CHARLSON}
    elix_tally = {k: 0 for k in ELIX}
    for h in all_hadm:
        cc = _resolve_charlson(hadm_charl.get(h, set()))
        charlson_cats[h] = sorted(cc)
        charlson_score[h] = sum(cw[c] for c in cc)
        for c in cc:
            charl_tally[c] += 1
        ec = _resolve_elix(hadm_elix.get(h, set()))
        vw_score[h] = sum(ew[c] for c in ec)
        elix_count[h] = len(ec)
        for c in ec:
            elix_tally[c] += 1
    print(f"[sev] diagnoses_icd {n} rows -> Charlson on {len(charlson_score)} hadm, "
          f"Elixhauser on {len(vw_score)} hadm", flush=True)
    return {"charlson_score": charlson_score, "charlson_cats": charlson_cats,
            "vw_score": vw_score, "elix_count": elix_count,
            "charl_tally": charl_tally, "elix_tally": elix_tally,
            "n_hadm": len(all_hadm)}


def _norepi_req():
    """Per-stay norepi requirement (median rate) from cache/mimic_norepi.csv."""
    import numpy as np
    stay = {}
    with open(NOREPI_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            try:
                rt = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rt <= 0 or rt > 5:
                continue
            stay.setdefault(row["stay_id"], []).append(rt)
    return {s: float(np.median(v)) for s, v in stay.items() if v}


def _load_labs():
    """cache/mimic_labs24h.csv -> {hadm: {lab: value}} or None if absent."""
    import numpy as np
    if not os.path.exists(LABS_CSV):
        return None
    labs = {}
    with open(LABS_CSV, newline="") as fh:
        r = _csv.DictReader(fh)
        cols = [c for c in (r.fieldnames or []) if c in _LAB_NAMES]
        for row in r:
            h = row.get("hadm_id")
            if not h:
                continue
            labs[h] = {c: (float(row[c]) if row.get(c) not in ("", None) else np.nan)
                       for c in cols}
    return labs if labs else None


def _gz(name):
    return gzip.open(os.path.join(MIMIC_RAW, name), "rt")


def _bootstrap_or(fit_design, death, seed, n_boot=400, col=0):
    """Bootstrap 95% CI for the OR of design column `col` (resample stays)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(seed)
    bs = []
    N = len(death)
    for _ in range(n_boot):
        idx = rng.integers(0, N, N)
        try:
            lr = LogisticRegression(max_iter=2000).fit(fit_design[idx], death[idx])
            bs.append(float(np.exp(lr.coef_[0][col])))
        except Exception:
            pass
    if not bs:
        return None, None
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def model():
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    req = _norepi_req()
    com = _comorbidity_scores()
    charlson_score = com["charlson_score"]
    vw_score = com["vw_score"]
    labs = _load_labs()

    # #vasopressors (cardiovascular-SOFA proxy)
    vaso = {}
    with open(VASO_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            vaso[row["stay_id"]] = int(row["n_vasopressors"])
    # stay -> hadm, subject
    stay_hadm, stay_subj = {}, {}
    with _gz("icustays.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            stay_hadm[row["stay_id"]] = row["hadm_id"]
            stay_subj[row["stay_id"]] = row["subject_id"]
    death = {}
    with _gz("admissions.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                death[row["hadm_id"]] = int(row.get("hospital_expire_flag", "0"))
            except (ValueError, TypeError):
                pass
    age = {}
    with _gz("patients.csv.gz") as fh:
        for row in _csv.DictReader(fh):
            try:
                age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                pass

    have_labs = labs is not None
    # Build the analysis matrix. Comorbidity scores default to 0 when a hadm has
    # NO mapped diagnosis (standard Charlson/Elixhauser convention: absence = 0).
    rows = []
    lab_cols = []
    if have_labs:
        # use the SOFA labs + lactate that are most consistently populated
        lab_cols = [c for c in ["lactate", "creatinine", "bilirubin", "platelets",
                                 "bun", "inr", "albumin", "anion_gap"]
                    if any(c in v for v in labs.values())]
    for sid, r in req.items():
        h = stay_hadm.get(sid)
        if not h or h not in death:
            continue
        a = age.get(stay_subj.get(sid), np.nan)
        nv = vaso.get(sid, 1)
        ch = charlson_score.get(h, 0)
        vw = vw_score.get(h, 0)
        base = [r, a, nv, ch, vw]
        if have_labs:
            lb = labs.get(h)
            if lb is None:
                continue
            labvals = [lb.get(c, np.nan) for c in lab_cols]
            rows.append(base + labvals + [death[h]])
        else:
            rows.append(base + [death[h]])

    arr = np.array([row for row in rows if all(np.isfinite(x) for x in row)], float)
    res = {"seed": SEED, "labs_present": have_labs,
           "n": int(len(arr)), "deaths": int(arr[:, -1].sum()) if len(arr) else 0,
           "lab_components": lab_cols if have_labs else [],
           "charlson_distribution": _dist(charlson_score),
           "vanwalraven_distribution": _dist(vw_score),
           "elix_count_distribution": _dist(com["elix_count"]),
           "charlson_prevalence": com["charl_tally"],
           "elixhauser_prevalence": com["elix_tally"]}
    if len(arr) < 500:
        res["note"] = f"only {len(arr)} complete rows"
        return res, com

    cols = arr.T
    reqv, ageA, nv, ch, vw = cols[0], cols[1], cols[2], cols[3], cols[4]
    dth = cols[-1].astype(int)
    lab_arrs = {}
    if have_labs:
        for i, c in enumerate(lab_cols):
            v = cols[5 + i]
            if c in _LAB_LOG:
                v = np.log(np.clip(v, 1e-6, None))
            lab_arrs[c] = v

    def std(v):
        s = v.std()
        return (v - v.mean()) / (s if s else 1.0)

    def or_and_auc(extra_cols, label):
        """Fit standardized logistic with requirement as col 0 + severity extras.
        Return requirement OR (per SD), bootstrap CI, and DeltaAUC the requirement
        adds over the severity-only model (same extras WITHOUT requirement)."""
        # severity-only AUC
        if extra_cols:
            Zsev = np.column_stack([std(c) for c in extra_cols])
            lr_s = LogisticRegression(max_iter=4000).fit(Zsev, dth)
            auc_sev = float(roc_auc_score(dth, lr_s.predict_proba(Zsev)[:, 1]))
        else:
            auc_sev = 0.5
        # +requirement
        design = np.column_stack([std(reqv)] + [std(c) for c in extra_cols])
        lr = LogisticRegression(max_iter=4000).fit(design, dth)
        or_req = float(np.exp(lr.coef_[0][0]))
        auc_full = float(roc_auc_score(dth, lr.predict_proba(design)[:, 1]))
        lo, hi = _bootstrap_or(design, dth, SEED, n_boot=400, col=0)
        return {"label": label, "or_per_sd": round(or_req, 3),
                "ci": [round(lo, 3), round(hi, 3)] if lo else None,
                "auc_severity_only": round(auc_sev, 3),
                "auc_plus_requirement": round(auc_full, 3),
                "delta_auc": round(auc_full - auc_sev, 4)}

    specs = []
    specs.append(or_and_auc([ageA], "a) age only"))
    specs.append(or_and_auc([ageA, ch], "b) +Charlson"))
    specs.append(or_and_auc([ageA, vw], "c) +van Walraven (Elixhauser)"))
    specs.append(or_and_auc([ageA, nv], "d) +#vasopressors"))
    if have_labs and lab_arrs:
        specs.append(or_and_auc([ageA] + list(lab_arrs.values()), "e) +lab-severity"))
        full_extra = [ageA, ch, vw, nv] + list(lab_arrs.values())
        specs.append(or_and_auc(full_extra, "f) FULL (age+Charlson+vanWalraven+#vaso+labs)"))
    else:
        full_extra = [ageA, ch, vw, nv]
        specs.append(or_and_auc(full_extra, "f) FULL (age+Charlson+vanWalraven+#vaso) [labs PENDING]"))

    res["specifications"] = specs

    # stability summary
    ors = [s["or_per_sd"] for s in specs]
    cis_above_1 = all(s["ci"] and s["ci"][0] > 1.0 for s in specs)
    or_age = specs[0]["or_per_sd"]
    or_full = specs[-1]["or_per_sd"]
    or_min, or_max = min(ors), max(ors)
    att = round(100 * (or_age - or_full) / (or_age - 1), 1) if or_age > 1 else None
    res["stability"] = {
        "or_age_only": or_age, "or_full": or_full,
        "or_range_across_specs": [round(or_min, 3), round(or_max, 3)],
        "attenuation_age_to_full_pct": att,
        "all_ci_lower_bounds_above_1": bool(cis_above_1)}

    stable = bool(or_full > 1.2 and cis_above_1 and (or_max - or_min) / or_max < 0.5)
    res["verdict"] = (
        f"Requirement->mortality OR per SD ranges {round(or_min,2)}-{round(or_max,2)} across "
        f"{len(specs)} severity specifications (age-only {or_age} -> FULL {or_full}; total "
        f"attenuation {att}%). " +
        ("STABLE and >1 across ALL specifications" +
         (" (incl. lactate+SOFA labs)" if have_labs else " (labs PENDING the labevents download)") +
         f", every 95% CI lower bound above 1{' ' if cis_above_1 else ' (NOT all CIs)'}-- the "
         "requirement carries mortality information BEYOND standard comorbidity/severity "
         "scoring; not merely 'sicker patients got more drug'."
         if stable else
         "COLLAPSES under comorbidity/severity adjustment -- the OR drops toward 1 and/or CIs "
         "cross 1; the mortality association is largely explained by measured severity. Honest: "
         "mostly a severity marker.") +
        (" Lab + FULL+labs specifications are PENDING (labevents download in progress at build "
         "time)." if not have_labs else "") +
        " CAVEAT: SOFA approximated by lab components + #vasopressors; no GCS / PaO2-FiO2 "
        "(chartevents). Observational.")
    return res, com


def _dist(d):
    """Summary distribution of a {key: numeric} mapping over its values."""
    import numpy as np
    if not d:
        return {}
    v = np.array(list(d.values()), float)
    return {"n": int(len(v)), "mean": round(float(v.mean()), 3),
            "sd": round(float(v.std()), 3),
            "median": round(float(np.median(v)), 3),
            "p25": round(float(np.percentile(v, 25)), 3),
            "p75": round(float(np.percentile(v, 75)), 3),
            "min": round(float(v.min()), 3), "max": round(float(v.max()), 3),
            "pct_zero": round(float((v == 0).mean()), 3)}


def _smoke_test(com):
    """Print a few sane-distribution checks on the Charlson/Elixhauser mapping."""
    print("\n[sev] === SMOKE TEST: comorbidity mapping sanity ===", flush=True)
    print(f"[sev] Charlson score dist: {_dist(com['charlson_score'])}", flush=True)
    print(f"[sev] van Walraven dist:   {_dist(com['vw_score'])}", flush=True)
    print(f"[sev] Elix group-count dist: {_dist(com['elix_count'])}", flush=True)
    ct = com["charl_tally"]
    top = sorted(ct.items(), key=lambda kv: -kv[1])[:8]
    print(f"[sev] top Charlson categories (hadm prevalence): {top}", flush=True)
    et = com["elix_tally"]
    top_e = sorted(et.items(), key=lambda kv: -kv[1])[:8]
    print(f"[sev] top Elixhauser groups (hadm prevalence): {top_e}", flush=True)
    # a couple of named hadms
    sample = list(com["charlson_cats"].items())[:3]
    for h, cats in sample:
        print(f"[sev]   hadm {h}: Charlson cats={cats} score={com['charlson_score'].get(h)} "
              f"vW={com['vw_score'].get(h)}", flush=True)


def _doc(res):
    L = ["# MIMIC-IV requirement -> mortality across MULTIPLE severity scores\n",
         "The 'signal vs just-sicker' question, hardened against several *standard* severity "
         "adjustments rather than one. Re-runs the norepinephrine-requirement->mortality OR per "
         "SD under: (a) age only, (b) +Charlson Comorbidity Index [Quan 2005 enhanced ICD-9-CM + "
         "ICD-10], (c) +van Walraven weighted Elixhauser [Quan 2005 codes, vanWalraven 2009 "
         "weights], (d) +#distinct-vasopressors [cardiovascular-SOFA proxy], "
         + ("(e) +lab-severity [first-24h labs], (f) FULL (all)."
            if res.get("labs_present") else
            "(f) FULL (all comorbidity); the lab-severity (e) and FULL+labs models are "
            "**PENDING** the labevents download (in progress at build time).") + "\n",
         f"- Complete-case stays: **{res.get('n')}** ({res.get('deaths')} deaths, rate "
         f"{round(res['deaths']/res['n'],3) if res.get('n') else 'NA'}). "
         f"Labs present: **{res.get('labs_present')}**"
         + (f"; lab components {res.get('lab_components')}." if res.get("labs_present") else ".")
         + "\n"]
    cd, vd = res.get("charlson_distribution", {}), res.get("vanwalraven_distribution", {})
    L += ["## Comorbidity score distributions (per hadm)",
          f"- **Charlson**: mean {cd.get('mean')} (SD {cd.get('sd')}), median {cd.get('median')} "
          f"[{cd.get('p25')}-{cd.get('p75')}], range {cd.get('min')}-{cd.get('max')}, "
          f"{cd.get('pct_zero')} with score 0 (n={cd.get('n')} hadm).",
          f"- **van Walraven (weighted Elixhauser)**: mean {vd.get('mean')} (SD {vd.get('sd')}), "
          f"median {vd.get('median')} [{vd.get('p25')}-{vd.get('p75')}], range {vd.get('min')}-"
          f"{vd.get('max')} (n={vd.get('n')} hadm).\n"]
    cp = res.get("charlson_prevalence", {})
    top = sorted(cp.items(), key=lambda kv: -kv[1])[:8]
    L += ["Top Charlson categories by hadm prevalence: "
          + ", ".join(f"{k} ({v})" for k, v in top) + ".\n"]
    if "specifications" in res:
        L += ["## Requirement -> mortality OR per SD: STABILITY TABLE across severity specs\n",
              "| Specification | Requirement OR/SD | 95% CI | AUC sev-only | AUC +req | DeltaAUC |",
              "|---|---|---|---|---|---|"]
        for s in res["specifications"]:
            ci = s["ci"]
            cis = f"[{ci[0]}, {ci[1]}]" if ci else "NA"
            L.append(f"| {s['label']} | {s['or_per_sd']} | {cis} | {s['auc_severity_only']} | "
                     f"{s['auc_plus_requirement']} | {s['delta_auc']} |")
        st = res.get("stability", {})
        L += ["",
              f"- OR range across specs: **{st.get('or_range_across_specs')}** "
              f"(age-only {st.get('or_age_only')} -> FULL {st.get('or_full')}; total attenuation "
              f"**{st.get('attenuation_age_to_full_pct')}%**).",
              f"- All 95% CI lower bounds above 1: **{st.get('all_ci_lower_bounds_above_1')}**.\n",
              "## Verdict", res["verdict"], ""]
    else:
        L += ["## Verdict", res.get("note", "insufficient complete rows"), ""]
    L += ["## Methods notes",
          "- **Charlson**: Quan et al. 2005 (Med Care 43:1130) enhanced ICD-9-CM AND ICD-10 code "
          "lists, 17 categories with standard integer weights (1/2/3/6). Per-row icd_version "
          "selects the ICD-9 vs ICD-10 prefix list. Hierarchy applied (metastatic supersedes any "
          "malignancy; diabetes-with-complication supersedes without; severe liver supersedes "
          "mild).",
          "- **Elixhauser**: Quan 2005 enhanced ICD-9-CM + ICD-10 group definitions (31 groups); "
          "summarized with the van Walraven (2009) integer point weights (the validated single "
          "score). Uncomplicated diabetes/solid-tumor collapsed when complicated/metastatic "
          "present.",
          "- Codes matched as PREFIXES against MIMIC's dot-free codes (e.g. ICD-9 '41401', ICD-10 "
          "'I2510'); hadms with no mapped diagnosis score 0 (standard convention).",
          "- Requirement = per-stay MEDIAN norepinephrine rate (0 < rate <= 5 mcg/kg/min). All "
          "models standardized logistic; requirement OR is per 1 SD. Bootstrap 95% CI resamples "
          "stays (400 reps, seed " + str(SEED) + ").",
          "- SOFA is APPROXIMATED by its lab components + #vasopressors; it still lacks the "
          "neurological (GCS) and respiratory (PaO2/FiO2) components, which live only in the 30GB "
          "chartevents. A complete SOFA could attenuate slightly further. Observational; "
          "norepinephrine dose is a known severity/mortality marker."]
    open(os.path.join(_DOCS, "MIMIC_SEVERITY_SCORES.md"), "w").write("\n".join(L) + "\n")


def main():
    try:
        st = os.statvfs(_CACHE)
        if st.f_bavail * st.f_frsize / 1e9 < 1.0:
            print("[sev] ABORT (disk-safe): <1GB free", flush=True)
            return
    except OSError:
        pass
    res, com = model()
    _smoke_test(com)
    json.dump(res, open(OUT_JSON, "w"), indent=2, default=float)
    _doc(res)
    print("\n[sev] VERDICT:", res.get("verdict", res.get("note")), flush=True)
    print("[sev] -> cache/mimic_severity_scores.json, docs/MIMIC_SEVERITY_SCORES.md", flush=True)


if __name__ == "__main__":
    main()
