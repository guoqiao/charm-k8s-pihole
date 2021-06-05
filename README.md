# charm-k8s-pihole

## Description

Pi-hole is a DNS sinkhole that protects your devices from unwanted content,
without installing any client-side software.
This Charm manages Pi-hole in Kubernetes cluster.
Powered by Charmed Operator Framework.

## Usage


    charmcraft build
    juju deploy ./pihole.charm pihole --resource pihole-image=pihole/pihole:latest
    juju deploy nginx-ingress-integrator ingress
    juju relate ingress pihole


## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
