import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Ask } from "./Ask";

const start = vi.fn();
let reviewState: { start: typeof start } = { start };
vi.mock("../lib/review", () => ({
  useReview: () => reviewState,
}));
vi.mock("../lib/api", () => ({ parseQuestion: vi.fn() }));
import { parseQuestion } from "../lib/api";

describe("Ask (dynamic PICO)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    reviewState = { start };
  });

  it("parses free text into editable PICO chips", async () => {
    vi.mocked(parseQuestion).mockResolvedValue({
      id: "q-novel",
      text: "Do ACE inhibitors reduce stroke?",
      pico: {
        population: "Adults with hypertension",
        intervention: "ACE inhibitor",
        comparator: "Placebo",
        outcome: "Stroke",
      },
      measure: "RR",
      trial_ids: ["NCT1", "NCT2"],
    });

    render(
      <MemoryRouter>
        <Ask />
      </MemoryRouter>
    );

    await userEvent.type(
      screen.getByLabelText("Clinical question"),
      "Do ACE inhibitors reduce stroke?"
    );
    await userEvent.click(screen.getByRole("button", { name: /Parse into PICO/i }));

    // PICO fields become editable inputs prefilled from the parse.
    expect(await screen.findByLabelText("Intervention")).toHaveValue("ACE inhibitor");
    expect(screen.getByLabelText("Outcome")).toHaveValue("Stroke");
    expect(screen.getByText(/2 candidate trials · pooling/)).toBeInTheDocument();
    // The parsed measure is preselected in the (now editable) measure dropdown.
    expect(screen.getByLabelText("Effect measure")).toHaveValue("RR");
    expect(screen.getByRole("button", { name: /Run review/i })).toBeInTheDocument();
  });

  it("starts empty — no autofill from any prior question", async () => {
    reviewState = { start };

    render(
      <MemoryRouter>
        <Ask />
      </MemoryRouter>
    );

    const box = screen.getByLabelText("Clinical question");
    // A fresh Ask never inherits the previous review's question.
    expect(box).toHaveValue("");

    await userEvent.type(box, "A brand new question?");
    expect(box).toHaveValue("A brand new question?");
  });
});
