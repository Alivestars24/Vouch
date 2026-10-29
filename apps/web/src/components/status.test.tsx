import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusTriptych } from "@/components/status";
import type { Check } from "@/lib/types";

const check: Check = {
  id: "check-1",
  submissionVersionId: "version-1",
  analysisStatus: "partial",
  machineAssessment: "human_review_required",
  reviewStatus: "unreviewed",
  invocationMode: "fixture",
  manifestHash: "a".repeat(64),
  reviewVersion: 1,
  rulePackName: "Review pack",
  rulePackVersion: "1.0",
  requiredCoverage: ["voice", "visual"],
  coverage: [],
  evidence: [],
  missingIntervals: [],
  findings: [],
  approvals: [],
};

describe("StatusTriptych", () => {
  it("keeps lifecycle, machine assessment, and human review visibly separate", () => {
    render(<StatusTriptych check={check} />);

    expect(screen.getByText("Analysis lifecycle")).toBeInTheDocument();
    expect(screen.getByText("Human Review Required")).toBeInTheDocument();
    expect(screen.getByText("Unreviewed")).toBeInTheDocument();
    expect(screen.getByText("Fixture result")).toBeInTheDocument();
  });
});
