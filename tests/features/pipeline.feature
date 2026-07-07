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
