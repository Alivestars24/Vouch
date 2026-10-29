import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MediaAssetMetadata, MediaModeNotice } from "@/components/media-processing";

afterEach(cleanup);

describe("independent media processing provenance", () => {
  it("labels fixture signature validation and synthetic time without implying a decoder ran", () => {
    render(<MediaModeNotice processing={{ mode: "fixture", processorVersion: "fixture-media-v1" }} />);
    expect(screen.getByText("Fixture media processing")).toBeInTheDocument();
    expect(screen.getByText(/signature-only validation and a synthetic 10-second timebase/)).toBeInTheDocument();
    expect(screen.getByText(/not observations of this upload/)).toBeInTheDocument();
  });

  it("keeps Check evidence synthetic even when media is decoded", () => {
    render(<MediaModeNotice processing={{ mode: "decoded", processorVersion: "ffmpeg-sandbox-v1" }} />);
    expect(screen.getByText("Decoded media processing")).toBeInTheDocument();
    expect(screen.getByText(/Decode failures are rejected/)).toBeInTheDocument();
    expect(screen.getByText(/Check providers still produce synthetic evidence/)).toBeInTheDocument();
  });

  it("does not assume fixture processing when capability information is missing", () => {
    render(<MediaModeNotice />);
    expect(screen.getByText("Media processing mode unavailable")).toBeInTheDocument();
    expect(screen.getByText(/Uploads are unavailable/)).toBeInTheDocument();
  });

  it("renders a measured asset snapshot without treating it as visual evidence or approval", () => {
    render(<MediaAssetMetadata metadata={{ mode: "decoded", processorVersion: "sandbox-v1", durationMs: 2432,
      width: 640, height: 360, frameRate: 24, audioPresent: false, normalizedSha256: "a".repeat(64),
      sourceTimeMapping: { kind: "identity", sourceOriginMs: 0, normalizedOriginMs: 0, precisionMs: 1 } }} />);
    expect(screen.getByText("Measured duration: 2.432 seconds")).toBeInTheDocument();
    expect(screen.getByText("Dimensions: 640 × 360 pixels")).toBeInTheDocument();
    expect(screen.getByText("Audio: Absent")).toBeInTheDocument();
    expect(screen.getByText(/Source-time mapping: identity/)).toHaveTextContent("1 ms precision");
    expect(screen.getByText(/not evidence of what the video depicts/)).toBeInTheDocument();
  });

  it("does not invent measured dimensions or audio data for fixture and legacy assets", () => {
    const view = render(<MediaAssetMetadata metadata={{ mode: "fixture", durationMs: 10000 }} />);
    expect(screen.getByText("Synthetic duration: 10 seconds")).toBeInTheDocument();
    expect(screen.queryByText(/Dimensions:|Audio:|Measured duration:/)).not.toBeInTheDocument();
    view.rerender(<MediaAssetMetadata />);
    expect(screen.getByText(/No processing snapshot is available/)).toBeInTheDocument();
    expect(screen.queryByText(/Synthetic duration:/)).not.toBeInTheDocument();
  });
});
