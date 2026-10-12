"""The Hannivoort triple interaction model: sevoflurane + propofol + remifentanil on ONE potency scale.

WHY THIS ONE. The investigator asked for a multi-drug model that accounts for synergy and is journal
defendable. `PKPD_MODEL_REVIEW.md` §6 Tier 3 rules out inventing an interaction surface, so the question
was whether a validated published one exists that can be implemented AS PUBLISHED. It does:

    Hannivoort LN, Vereecke HE, Proost JH, Heyse BE, Eleveld DJ, Bouillon TW, Struys MM, Luginbuhl M.
    "Probability to tolerate laryngoscopy and noxious stimulation response index as general indicators of
    the anaesthetic potency of sevoflurane, propofol, and remifentanil."
    Br J Anaesth 2016;116(5):624-31.  PMID 27106965.   (verified from the MEDLINE record, rule 25)

THE PARAMETERS ARE IN THE ABSTRACT, WHICH IS WHY THE PAYWALL DOES NOT BLOCK THIS. Quoted verbatim so a
reader can check every number against the source (rule 42 -- a quotation supports only what it says):

    "Sevoflurane and propofol interact additively, whereas remifentanil interacts in a strongly
     synergistic manner. The effect-site concentrations of sevoflurane and propofol at a PTOL of 50%
     (Ce50; se) were 2.59 (0.13) vol % and 7.58 (0.49) ug ml(-1). A CeREMI of 1.36 (0.15) ng ml(-1)
     reduced the Ce50 of sevoflurane and propofol by 50%. The common slope factor was 5.22 (0.52)."

WHAT IS QUOTED AND WHAT IS INFERRED, KEPT SEPARATE. The four numbers and the two interaction statements
are quoted. The EQUATION below is an inference -- the standard normalised-units form that those statements
specify up to convention -- because the paper's equation is behind a paywall. Labelled as an inference
rather than presented as the source's content, which is rule 42's whole point.

    U_hypnotic = Ce_sevo / 2.59  +  Ce_prop / 7.58            <- "interact additively"
    U          = U_hypnotic * (1 + Ce_remi / 1.36)            <- "reduced the Ce50 ... by 50%" at 1.36
    PTOL       = U^5.22 / (1 + U^5.22)                        <- PTOL = 50% at U = 1, slope 5.22

Halving a Ce50 is the same as doubling the normalised units the same concentration buys, hence the
multiplicative form; and it is multiplicative rather than additive in remifentanil because an opioid alone
does not produce the effect. That last point is not an assumption -- Bouillon 2004 (PMID 15166553)
measured it: "Remifentanil alone had no appreciable effect on response to shaking and shouting or response
to laryngoscopy." The form reproduces that exactly (U -> 0 as the hypnotics go to zero, whatever the
opioid), and `tests/test_interaction.py` checks it.

**THE SLOPE FACTOR IS IRRELEVANT TO EVERY RANK-BASED STATISTIC IN THIS PROJECT**, and that is worth knowing
before anyone worries about the exact equation. `PTOL` is a strictly increasing function of `U`, so any
Spearman correlation, AUC, or rank-based increment computed on PTOL is identical to the one computed on U.
The functional-form inference therefore cannot change a rank-based result; only the combination rule can,
and the combination rule is quoted rather than inferred. Use `potency_units` when the statistic is
rank-based and `ptol` only when a probability is actually wanted.

WHAT IS NOT IMPLEMENTED, AND WHY.
  * **NSRI.** The abstract says the NSRI "was derived from PTOL" but does not give the mapping, and
    Luginbuhl's scaling is not quoted anywhere available here. Implementing a guessed rescaling would be
    inventing a relation. `ptol` is the quantity the abstract fully specifies; NSRI is a monotone
    rescaling of it, so nothing rank-based is lost.
  * **Uncertainty propagation from the standard errors.** They are recorded in `PARAM_SE` and can be used
    for a sensitivity arm, but no fitted covariance is available and pretending the four are independent
    would be an invention.

THE LIMIT THAT TRAVELS WITH EVERY USE OF THIS, stated before any result (rule 47). Wang et al. 2017
(Medicine 96:e6895, PMID 28489797) reports that "a previously published propofol-remifentanil response
surface model does not predict patient response well in video-assisted thoracic surgery." A published
surface is a population model transported to a new population, and this project's own PK validation
measured what transport costs: a fixed kernel reproduced a pump's Ce at MDAPE 54.9 % across patients while
fitting each patient at R2 0.9990 (`PKPD_MODEL_REVIEW.md`, `PK_VALIDATION_NOTE.md`). Expect the same shape
here -- good ORDERING, poor absolute calibration -- which is exactly why the rank-based note above matters.
"""
from __future__ import annotations

# Quoted from the abstract of PMID 27106965. Values, then standard errors, kept separately so a
# sensitivity arm cannot silently use a point estimate where an interval was meant.
CE50_SEVO_VOL_PCT = 2.59
CE50_PROP_UG_ML = 7.58
C50_REMI_NG_ML = 1.36
SLOPE = 5.22

PARAM_SE = {"ce50_sevo": 0.13, "ce50_prop": 0.49, "c50_remi": 0.15, "slope": 0.52}
SOURCE_PMID = 27106965


def potency_units(ce_sevo=0.0, ce_prop=0.0, ce_remi=0.0,
                  ce50_sevo=CE50_SEVO_VOL_PCT, ce50_prop=CE50_PROP_UG_ML,
                  c50_remi=C50_REMI_NG_ML):
    """Normalised anaesthetic potency `U`. U = 1 is the PTOL-50 surface.

    Units are the source's: sevoflurane in vol % (END-TIDAL, since that is what approximates the effect
    site -- an inspired reading would overstate it), propofol in ug/ml, remifentanil in ng/ml. Passing
    a MAC value where vol % is expected would be a silent factor of about 2 (1 MAC sevoflurane is ~2 vol %
    in a young adult and less in an old one), so callers converting from MAC must do so explicitly.

    **Prefer this over `ptol` whenever the downstream statistic is rank-based** -- it is monotonically
    related to PTOL and does not depend on the slope factor, which is the one parameter the equation
    inference could get wrong.
    """
    import numpy as np
    s = np.asarray(ce_sevo, dtype=float)
    p = np.asarray(ce_prop, dtype=float)
    r = np.asarray(ce_remi, dtype=float)
    # Negative concentrations are a data error, not a small effect: clamp and let the caller's own
    # coverage checks see the zeros rather than silently producing negative potency.
    s = np.where(np.isfinite(s) & (s > 0), s, 0.0)
    p = np.where(np.isfinite(p) & (p > 0), p, 0.0)
    r = np.where(np.isfinite(r) & (r > 0), r, 0.0)
    u_hyp = s / ce50_sevo + p / ce50_prop
    return u_hyp * (1.0 + r / c50_remi)


def ptol(ce_sevo=0.0, ce_prop=0.0, ce_remi=0.0, slope=SLOPE, **kw):
    """Probability of TOLERATING laryngoscopy, in [0, 1]. 0.5 exactly on the U = 1 surface."""
    import numpy as np
    u = potency_units(ce_sevo, ce_prop, ce_remi, **kw)
    with np.errstate(over="ignore", invalid="ignore"):
        v = np.power(np.clip(u, 0.0, None), slope)
        out = v / (1.0 + v)
    return np.where(np.isfinite(out), out, np.where(u > 1.0, 1.0, 0.0))


def mac_to_vol_pct_sevo(mac, age_years=None):
    """Convert age-adjusted MAC to sevoflurane vol %, or refuse.

    VitalDB publishes `Primus/MAC`, which is an age-adjusted MAC MULTIPLE, while `potency_units` wants
    vol %. The conversion needs MAC_40 for sevoflurane and Mapleson's age correction, and **this project
    has not verified either from a primary source**, so the function raises rather than guessing. It
    exists to make the unit mismatch impossible to make silently -- rule 42's habit applied to units.
    """
    raise NotImplementedError(
        "MAC -> vol % needs a verified MAC_40 and an age-correction relation, neither of which has been "
        "taken from a primary source in this project. Use Primus/EXP_SEVO (end-tidal vol %) directly, "
        "which VitalDB records in the same 3,687 cases, rather than converting from MAC.")
