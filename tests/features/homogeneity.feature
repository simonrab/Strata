Feature: Homogeneity gate before pooling
  Cochrane requires that only trials similar enough in population, intervention,
  comparator and outcome be pooled. The pipeline surfaces clinical diversity and
  statistical heterogeneity and withholds the pooled estimate until a reviewer
  confirms — but it never blocks a clearly homogeneous, low-heterogeneity set.

  Scenario: Homogeneous trials pool without a gate
    Given the locked GLP-1 MACE question
    And ClinicalTrials.gov results are served from recorded fixtures
    When the review pipeline runs
    Then the homogeneity gate does not require confirmation
    And the pooled hazard ratio rounds to 0.86

  Scenario: Withhold pooling until a reviewer confirms clinically diverse trials
    Given a clinically diverse question whose trial effects scatter widely
    When the review pipeline runs
    Then pooling is withheld pending confirmation
    When a reviewer confirms the trials are combinable
    Then the trials are pooled and the confirmation is recorded
