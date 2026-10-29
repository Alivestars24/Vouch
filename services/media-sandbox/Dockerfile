# Official Python multi-platform digest verified 2026-10-22; no runtime network required.
FROM python:3.14-slim-bookworm@sha256:945c2676dc2b18e0c1f16879244122c57c0ffede60006bf3df159c507a31bcae
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg=7:5.1.9-0+deb12u1 \
    && rm -rf /var/lib/apt/lists/*
COPY --chmod=0555 wrapper.py /opt/vouch-media/wrapper.py
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["python", "-I", "-B", "/opt/vouch-media/wrapper.py"]
