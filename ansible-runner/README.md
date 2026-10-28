# ansible-runner

Forgejo Actions job image with the `vault` CLI and Ansible (`ansible.windows`
included). `publish` rebuilds and pushes it every 30 minutes as
`gitea.acme.anvil/wile.coyote/ansible-runner:latest`.

Use it from a workflow:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    container:
      image: gitea.acme.anvil/wile.coyote/ansible-runner:latest
```

## One-time setup on elmer

Add a top-level `container:` section to `/etc/data/config.yaml`, next to the
existing `server:` and `runner:` (restart the runner after):

```yaml
container:
  # Use the image already in elmer's Docker instead of pulling every job,
  # so deploys work without the registry/internet.
  force_pull: false
  # publish.yml runs docker build/push, so job containers need the socket.
  # Note: any job on this runner can then control elmer's Docker.
  valid_volumes:
    - /var/run/docker.sock
  options: -v /var/run/docker.sock:/var/run/docker.sock
```

Forgejo is plain HTTP, so allow it in `/etc/docker/daemon.json`
(then `systemctl restart docker`):

```json
{ "insecure-registries": ["gitea.acme.anvil"] }
```

Repo secret `REGISTRY_TOKEN`: a Forgejo access token with `write:package`.
Only `:latest` is pushed. Layers it replaces stay on Forgejo's disk until its
package cleanup runs (admin cron `cleanup_packages`), so make sure that's
enabled.
