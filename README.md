# wrccdc2027-inv2-wilee
"declarative" configuration for wilee.acme.anvil, windows 11 pro box

non-declarative parts:
- db setup on marvin
- ssh ca setup on marvin
- forgejo runner / forgejo source code for gallery service

included components:
- disabling defender
- disabling firewall
- don't save shell history
- hmailserver
- xampp / roundcube
- git / python via chocolatey
- configuring ssh ca (black team / marvin vault)
- prometheus windows exporter

sub-repositories:
- gallery app (custom python app with wile e coyote gifs)
- ansible-runner (dockerfile with forgejo action to build a docker container w/ hashicorp vault cli and ansible preinstalled)

commits for sub-repositories are merged with the commit history of the main repo.
