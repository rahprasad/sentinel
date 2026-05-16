# Wrapper that lets Zeabur build the AgentField FOSS control plane.
# The upstream image already has CMD/EXPOSE/healthcheck baked in — this
# Dockerfile exists only to give Zeabur a substantive build context
# (a FROM-only Dockerfile gets detected as static).
FROM agentfield/control-plane:latest

LABEL org.opencontainers.image.title="agentfield-control-plane"
LABEL org.opencontainers.image.source="https://github.com/Agent-Field/agentfield"
LABEL service="sentinel-agentfield-control-plane"

# Mark the build so Zeabur's plantype detector sees a Docker pipeline.
RUN echo "sentinel-agentfield-control-plane $(date -u +%Y-%m-%d)" > /etc/sentinel-build.txt

EXPOSE 8080
