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
