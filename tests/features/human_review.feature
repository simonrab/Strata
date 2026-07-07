Feature: Human confirm and flag decisions feed the pool
  The trust story's human-in-the-loop gate: a reviewer's flag removes a trial
  from the pooled estimate and its decision persists to the audit trail, while a
  confirm records sign-off without changing the pool.

  Scenario: A reviewer flags a trial and the pool re-runs without it
    Given a pooled review of the eight GLP-1 MACE trials
    When a reviewer flags the first trial for review
    Then the re-pooled review includes seven trials
    And the flagged trial is excluded from the pool
    And the decision is saved to the audit trail
