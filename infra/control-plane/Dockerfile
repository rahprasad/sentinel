# Thin wrapper so Zeabur can deploy the AgentField FOSS control plane via
# `zeabur deploy --create --name agentfield-control-plane` from this directory.
#
# The upstream image already has the right CMD/EXPOSE/healthcheck baked in —
# this Dockerfile exists only to give Zeabur a build context to push.
FROM agentfield/control-plane:latest

EXPOSE 8080
