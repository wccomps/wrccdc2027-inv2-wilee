# Job image for Forgejo Actions: the stock act image plus the vault CLI and
# Ansible (with ansible.windows), so deploy workflows need no install steps
# or internet. Built and pushed to the Forgejo registry by
# .forgejo/workflows/publish.yml; workflows use it with
#
#   container:
#     image: gitea.acme.anvil/wile.coyote/ansible-runner:latest
FROM ghcr.io/catthehacker/ubuntu:act-22.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends gnupg lsb-release openssh-client python3-pip \
 && curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/hashicorp.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends vault \
 && rm -rf /var/lib/apt/lists/*

# 22.04 ships Python 3.10; ansible-core 2.18+ needs 3.11 on the controller.
RUN pip3 install --no-cache-dir "ansible-core>=2.16,<2.18" \
 && ansible-galaxy collection install -p /usr/share/ansible/collections ansible.windows
