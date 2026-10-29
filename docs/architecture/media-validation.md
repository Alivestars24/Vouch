# Bounded local media validation

Date: 2026-10-22; reviewed 2026-10-23. Status: implemented and locally verified; command evidence is
in [implementation status](../engineering/implementation-status.md).
This follows [retention](retention-worker.md) and preserves original assets and historical approvals.

## Supported outcome

Media processing and model invocation are independent. `VOUCH_MEDIA_MODE=fixture` preserves
deterministic synthetic workflow tests; `decoded` probes, fully decodes and transiently normalizes
authorized MP4/WebM in a bounded local Docker sandbox. Provider mode stays `fixture`, and the UI
must not describe fixture evidence as observations of the uploaded video. Decoding failure never
falls back to a fixture success. Deployment remains disabled.

The initial envelope is at most 5 MB, one video stream and at most one audio stream, a positive
duration up to 30 seconds, at most 1920x1080 pixels and 60 fps. Reject encrypted/corrupt files,
unsupported streams and ambiguous/non-monotonic timing. Only an identity mapping from normalized
presentation time to original presentation time is supported initially; both origins are the first
presented source frame at zero. Reject unsupported offsets/discontinuities instead of inventing
source evidence timestamps. Providers must respect the measured duration.

## Isolation and data lifecycle

Use a typed `MediaProcessor` interface. The decoded implementation passes bytes through stdin to a
locally built, pinned sandbox image; no caller JWT, signed URL, source path, environment secret or
Docker socket enters it. Run non-root, network-none, read-only root, dropped capabilities,
no-new-privileges, one CPU, 512 MB/no extra swap, bounded processes/tmpfs and no persistent container
logs. FFmpeg accepts only local file/pipe protocols. A host watchdog must remove the exact named
container after timeout; terminating the Docker client alone is insufficient.

The wrapper writes/probes/fully decodes/normalizes inside tmpfs, returns only bounded JSON metadata
and a normalized SHA-256, then exits. Normalized bytes are discarded; they are not yet reusable
provider artifacts. There are no extra retained media copies for the retention worker. Reusable
private derivatives and live-worker read authority need a separate contract. Docker daemon access
is privileged: this is a local safety boundary, not a production sandbox certification.

## Publication and version integrity

Finalization snapshots the authorized asset and bytes, commits before download/decoding, then
re-locks and rechecks current membership, uploader authorization, immutable content/hash, state,
capability/deadline and tombstones before publication. Deletion during processing wins; a late
decoder cannot restore source metadata or make the asset usable. Do not hold database locks across
Storage HTTP or the decoder. No raw decoder stderr, bytes or source filenames enter API errors/logs.

The existing bounded content PUT retains its source-row lock across Storage upload. Releasing that
lock needs a separate late-upload/cleanup handoff protocol; this slice does not weaken deletion
ordering to remove it. Finalization alone is split around external work.

### Temporary-copy deletion boundary

Review identified that a tombstone alone cannot erase a still-running decoder's tmpfs. Before
releasing the source lock, prepare an empty, non-running container and persist its exact scoped
name and bounded processing lease on the source. Preparation transfers no media. External work
may only start that already-created container; it cannot recreate a removed name. Deletion takes
the same source/lineage locks, records a `local_media_sandbox` destination, removes the exact
container and confirms absence. A later decoder start then fails rather than creating a copy
after a completed receipt. Cleanup/runtime unavailability stays partial/retryable, not completed.

Names include opaque organization/asset UUIDs plus a random run ID. Cleanup validates that tenant
scope and never removes a broad name prefix. Retries cannot replace a prior run reference until
its container absence is confirmed; a live processing lease returns an explicit conflict. These
two small source fields reuse the existing deletion outbox rather than adding another queue or
assuming elapsed time proves erasure. Normal completion also confirms container removal before
publishing measured metadata. Only empty-container preparation may briefly hold the source lock;
no personal bytes or untrusted decoding cross that transaction.

Persist media mode, processor version, measured duration, dimensions/frame rate/audio presence,
normalized hash and explicit source-time mapping. Source hash remains the original bytes. New
analysis manifests include processing metadata; legacy fixtures/historical approvals retain their
existing binding. Fixture evidence remains labeled synthetic even for a decoded upload.

## Proof and operation

Default tests remain Docker/network/paid-call free through the fixture processor and deterministic
failure doubles. Provide an explicit sandbox image build command and opt-in real synthetic MP4/
WebM smoke tests. Verify truncated/header-only media, unsupported limits/timing, missing runtime,
watchdog cleanup, bounded output and deletion races. Exercise the existing authenticated browser
workflow with explicit fixture media until valid decoded fixtures are wired; document that mode
truthfully. Do not silently change generated authenticated configuration to decoded until the image
and real decode path pass. Record commands/results and remaining gates in implementation status.
