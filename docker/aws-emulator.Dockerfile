# AWS Emulator (local AWS API emulator, CC0-1.0) for offline infrastructure tests.
#
# AWS does not publish a prebuilt image; this follows the official Docker guide
# (docs.aws.amazon.com/emulator/latest/userguide/getting-started-docker.html).
# State lives in memory only and is lost when the container stops.
#
# Build:  docker compose --profile emulator build aws-emulator
# Use:    infra/aws/recurrent-depth/scripts/emulator-e2e.sh
#
# Publish the port on 127.0.0.1 only. The emulator accepts any request when
# auth is off, so it must never be reachable from the network.

FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal

ARG TARGETARCH
# Override to pin a specific build, e.g. .../LTS/<version>/aws-emulator-x86_64.rpm
ARG EMULATOR_CHANNEL_URL=https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest

RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "aarch64" || echo "x86_64") \
    && curl -fsSL "${EMULATOR_CHANNEL_URL}/aws-emulator-${ARCH}.rpm" -o /tmp/aws-emulator.rpm \
    && rpm -i /tmp/aws-emulator.rpm \
    && rm /tmp/aws-emulator.rpm \
    && mkdir -p /home/emulator/.aws/emulator \
    && chown -R 1000 /home/emulator

USER 1000
ENV HOME=/home/emulator \
    EMULATOR_BIND_ADDRESS=0.0.0.0 \
    EMULATOR_TELEMETRY=off

ENTRYPOINT ["aws-emulator", "--telemetry", "off"]
