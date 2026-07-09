Feature: Living meta-analysis pipeline
  The whole spine, end to end: a locked clinical question travels from retrieval
  through extraction, deterministic validation, and pooling to an auditable
  answer that matches the published meta-analysis.

  Scenario: Pool the GLP-1 MACE question to the published answer
    Given the locked GLP-1 MACE question
    And ClinicalTrials.gov results are served from recorded fixtures
    When the review pipeline runs
    Then every trial is extracted with provenance and none are flagged
    And the pooled hazard ratio rounds to 0.86
    And the confidence interval shows a significant cardiovascular benefit
    And the plain-language summary reports the benefit

  Scenario: Pool a continuous outcome on the natural scale
    Given a continuous-outcome question with two trials reporting mean, SD and n
    When the review pipeline runs
    Then the pooled mean difference stays on the natural scale
    And each pooled study carries a provenance snippet

  Scenario: Pool a rare binary outcome with Peto
    Given a rare binary-outcome question with a zero-event arm
    When the review pipeline runs
    Then the pool uses the Peto one-step odds ratio

  Scenario: Read a trial that lacks structured CT.gov results from its abstract
    Given a question whose trial is a Europe PMC publication read by Claude
    When the review pipeline runs
    Then the trial is extracted from the published text with provenance
