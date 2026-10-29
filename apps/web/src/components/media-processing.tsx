import { InlineNotice } from "@/components/status";
import type { MediaProcessing, MediaProcessingMetadata } from "@/lib/types";

export function MediaModeNotice({ processing, loading = false }: { processing?: MediaProcessing; loading?: boolean }) {
  if (loading) return <InlineNotice tone="neutral" title="Verifying media processing mode"><p>The API is checking the configured media validation path before uploads are enabled.</p></InlineNotice>;
  if (!processing) {
    return <InlineNotice tone="warning" title="Media processing mode unavailable"><p>The API has not verified its media processing mode. Uploads are unavailable until you refresh the campaign and configuration is verified.</p></InlineNotice>;
  }
  return (
    <InlineNotice tone="neutral" title={processing.mode === "fixture" ? "Fixture media processing" : "Decoded media processing"}>
      <p>{processing.mode === "fixture"
        ? "Uploads receive signature-only validation and a synthetic 10-second timebase. The file is not decoded."
        : "Uploads are fully decoded and transiently normalized locally within configured limits. Decode failures are rejected, never replaced with a fixture success."}</p>
      <p>Check providers still produce synthetic evidence, not observations of this upload. Decoding is not human approval.</p>
    </InlineNotice>
  );
}

export function MediaAssetMetadata({ metadata }: { metadata?: MediaProcessingMetadata }) {
  if (!metadata) {
    return <p>No processing snapshot is available for this legacy or removed asset.</p>;
  }
  const duration = metadata.durationMs !== undefined
    ? `${(metadata.durationMs / 1000).toLocaleString("en-IN", { maximumFractionDigits: 3 })} seconds`
    : undefined;
  return (
    <div>
      <p><strong>Selected asset: {metadata.mode === "decoded" ? "Decoded media" : "Fixture media"}</strong></p>
      {duration ? <p>{metadata.mode === "decoded" ? "Measured duration" : "Synthetic duration"}: {duration}</p> : null}
      {metadata.width && metadata.height ? <p>Dimensions: {metadata.width} × {metadata.height} pixels</p> : null}
      {metadata.frameRate ? <p>Frame rate: {metadata.frameRate} fps</p> : null}
      {metadata.audioPresent !== undefined ? <p>Audio: {metadata.audioPresent ? "Present" : "Absent"}</p> : null}
      {metadata.sourceTimeMapping ? <p>Source-time mapping: identity ({metadata.sourceTimeMapping.sourceOriginMs} ms source → {metadata.sourceTimeMapping.normalizedOriginMs} ms normalized){metadata.sourceTimeMapping.precisionMs !== undefined ? `; ${metadata.sourceTimeMapping.precisionMs} ms precision` : ""}.</p> : null}
      {metadata.normalizedSha256 ? <p>Normalized hash: <code title={metadata.normalizedSha256}>{metadata.normalizedSha256.slice(0, 12)}…</code></p> : null}
      {metadata.processorVersion ? <p>Processor: {metadata.processorVersion}</p> : null}
      <p>Processing metadata is not evidence of what the video depicts.</p>
    </div>
  );
}
