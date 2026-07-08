"""The locked demo question: GLP-1 receptor agonists and cardiovascular events.

A recent, well-established meta-analysis (Sattar et al., Lancet Diabetes
Endocrinol 2021) pools these 8 cardiovascular outcome trials to a MACE hazard
ratio of ~0.86 (0.80-0.93) — a result judges can sanity-check.
"""

from .schema import PICO, EffectMeasure, Question

# 3-point MACE cardiovascular outcome trials of GLP-1 receptor agonists.
GLP1_CVOT_TRIALS = [
    "NCT01147250",  # ELIXA (lixisenatide)
    "NCT01179048",  # LEADER (liraglutide)
    "NCT01720446",  # SUSTAIN-6 (semaglutide s.c.)
    "NCT01144338",  # EXSCEL (exenatide)
    "NCT02465515",  # HARMONY OUTCOMES (albiglutide)
    "NCT01394952",  # REWIND (dulaglutide)
    "NCT02692716",  # PIONEER-6 (oral semaglutide)
    "NCT03496298",  # AMPLITUDE-O (efpeglenatide)
]

GLP1_MACE_QUESTION = Question(
    id="glp1-mace",
    text=(
        "In adults with type 2 diabetes or high cardiovascular risk, do GLP-1 "
        "receptor agonists versus placebo reduce major adverse cardiovascular "
        "events (MACE)?"
    ),
    pico=PICO(
        population="Adults with type 2 diabetes or established cardiovascular risk",
        intervention="GLP-1 receptor agonist",
        comparator="Placebo",
        outcome="3-point MACE (CV death, non-fatal MI, non-fatal stroke)",
    ),
    measure=EffectMeasure.HR,
    trial_ids=GLP1_CVOT_TRIALS,
)

# The living-layer demo: seed the review as it stood *before* the last CVOT read
# out, then inject that trial to reach today's published 8-trial answer. AMPLITUDE-O
# (efpeglenatide, 2021) is the most-recent readout and its fixture already exists.
HELD_OUT_TRIAL = "NCT03496298"  # AMPLITUDE-O
GLP1_BASELINE_QUESTION = GLP1_MACE_QUESTION.model_copy(
    update={"trial_ids": GLP1_CVOT_TRIALS[:7]}
)


def seed_baseline(store, fetch_study):
    """Persist the 7-trial baseline (v1) so the demo can inject the eighth.

    Goes through `run_review_collect` directly rather than the MCP `run_review`
    tool, whose `_resolve_question` special-cases the glp1-mace id back to the
    full 8-trial question — which would erase the diff the demo exists to show.
    """
    from .pipeline import run_review_collect  # local: avoid import-time weight

    result = run_review_collect(GLP1_BASELINE_QUESTION, fetch_study)
    store.save_snapshot(result)
    return result
