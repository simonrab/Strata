Feature: A new trial's change surfaces on the dashboard
  The living layer's promise, end to end over REST: when a new trial lands, the
  review re-pools, the evidence base grows, and the dashboard reflects that the
  estimate moved — without a human touching the numbers.

  Scenario: Injecting the eighth GLP-1 trial updates the dashboard
    Given a seeded 7-trial GLP-1 MACE baseline
    When the eighth trial is injected via the REST update endpoint
    Then the update reports eight pooled trials
    And the dashboard row shows eight trials
    And the dashboard status is "estimate-updated"
