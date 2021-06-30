# Charmed Kubernetes Operator for Pi-hole

Deploy [Pi-hole](https://pi-hole.net/) in Kubernetes with [Juju](https://juju.is/docs) and [Charmed Operator Framework](https://juju.is/docs/sdk).

Pi-hole is a DNS sinkhole that protects your devices from unwanted content,
without installing any client-side software.
This Charm manages Pi-hole in Kubernetes cluster, such as MicroK8s.
Powered by Charmed Operator Framework.

## Quickstart

    charmcraft pack
    juju deploy ./pihole.charm pihole --resource pihole-image=pihole/pihole:latest  # from local
    juju deploy pihole  # or from charmhub
    juju deploy nginx-ingress-integrator ingress
    juju relate ingress pihole
    watch --color juju status --color

## Development

Update the ingress library:

    charmcraft fetch-lib charms.ingress.v0.ingress

refer to [Nginx Ingress Integrator](https://charmhub.io/nginx-ingress-integrator/configure).

Set up a local dev/test env with MicroK8s:

    sudo snap install --classic juju microk8s
    sudo snap install charmcraft
    sudo snap alias microk8s.kubectl kubectl
    newgrp microk8s
    sudo usermod -aG microk8s $(whoami)
    # logout or reboot to make the change system-wide
    microk8s enable storage dns ingress dashboard
    juju bootstrap microk8s microk8s
    juju add-model dev

Build charm, deploy/upgrade:

    charmcraft build
    juju deploy ./pihole.charm pihole --resource pihole-image=pihole/pihole:latest
    juju upgrade-charm --path ./pihole.charm pihole

Describe/inspect pod (juju unit):

    microk8s kubectl describe -n dev pod pihole-0

Show logs:

    juju debug-log --include unit-pihole-0  # juju log
    microk8s kubectl logs -f -n dev pod/pihole-0 -c pihole  # docker log

Access charm/sidecar or pihole/app container:

    juju ssh --container charm  pihole/0
    juju ssh --container pihole pihole/0
    # in microk8s env, above is equvalent to:
    microk8s kubectl exec -n dev -it pihole-0 -c charm  -- bash
    microk8s kubectl exec -n dev -it pihole-0 -c pihole -- bash

Run command in containers:

    microk8s kubectl exec -n dev -it pihole-0 -c pihole -- /charm/bin/pebble plan
    microk8s kubectl exec -n dev -it pihole-0 -c pihole -- /charm/bin/pebble services
    microk8s kubectl exec -n dev -it pihole-0 -c charm -- ps aux

The expected juju run equvalent should be:

    juju run --unit pihole/0 -- /charm/bin/pebble <cmd>
    juju run --unit pihole/0 --operator -- ps aux

However, this seems not working because of [bug 1934046](https://bugs.launchpad.net/juju/+bug/1934046)

## Access Kubernetes Dashboard

Get token:

    token=$(microk8s kubectl -n kube-system get secret | grep default-token | cut -d " " -f1)
    microk8s kubectl -n kube-system describe secret $token

Find IP:

    microk8s kubectl get all -A | grep service/kubernetes-dashboard
    kube-system           service/kubernetes-dashboard        ClusterIP   10.152.183.231   <none>        443/TCP

Access url in browser:

    https://10.152.183.231

The browser may show error:

    Your connection isn't private
    NET:ERR_CERT_INVALID

and in latest chrome/edge browser, there is no `advanced` button any more.

To bypass: click anywhere blank on the page, then type `thisisunsafe`.

Or enable setting:

    chrome://flags/#allow-insecure-localhost
    edge://flags/#allow-insecure-localhost

Now you should see the dashboard, copy/paste the token in, you will login in.
Switch to the `dev` namespace to see your pods.

## Testing

    git clone git@github.com:guoqiao/charm-k8s-pihole.git && cd charm-k8s-pihole
    sudo apt update && sudo apt install -y python3-virtualenv
    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt
    ./run_tests

## Publish to CharmHub

    charmcraft login
    charmcraft whoami

    charmcraft register pihole
    charmcraft names

    IMG=pihole/pihole:latest
    docker pull $IMG
    charmcraft upload-resource --image=$IMG pihole pihole-image

    charmcraft pack
    charmcraft upload pihole.charm

    # check current revisions
    charmcraft revisions pihole
    charmcraft resource-revisions pihole pihole-image

    # attach a resource to a relese if necessary
    charmcraft release pihole --revision=1 --resource=pihole-image:1 --channel=edge
    # you can release multiple channels together
    charmcraft release pihole --revision=2 --resource=pihole-image:2 --channel=edge --channel=beta --channel=candidate --channel=stable
    charmcraft status

NOTE: CharmHub uses info from `stable` channel to populate charm's homepage.

## Use Pi-hole as DNS server on Ubuntu

In a browser tab, open a website with ads, e.g.:  https://www.speedtest.net/

Find Pi-hole IP, test it's working with:

    host google.com $IP

At Settings -> Wi-Fi -> select a connection -> Gear Icon -> IPv4 -> DNS:

- Disable Automatic
- Add Pi-hole IP in
- Connect to this Wi-Fi

Then ensure system is using expected DNS:

    sudo systemd-resolve --flush-caches
    sudo service network-manager restart
    ip link; IF=<interface>  # e.g.: wlp2s0
    nmcli device show $IF | grep DNS  # should be the Pi-hole IP

Now in another browser tab, open the site again to compare. You should see the ad blocks are gone.

## Issues

- how to expose pihole dns service to home/office network
- how to expose TCP/UDP ports (53, 67) in charm
- need easy way to run one-off cmd
- service stop not working properly (s6-init)
- [Error: ImagePullBackOff](https://pastebin.ubuntu.com/p/gtKKBNZ6hp/)
- webpassword in config(pihole only stores hashed password, no way to show it)

## Useful docs

- [charmhub homepage](https://charmhub.io/pihole)
- [issue tracker docs](https://discourse.charmhub.io/t/pi-hole-kubernetes-operator-charm-docs/4763)
- [pihole docker image](https://hub.docker.com/r/pihole/pihole)
- [charm metadata v2 doc](https://discourse.charmhub.io/t/charm-metadata-v2/3674)
- [sdk pebble doc](https://juju.is/docs/sdk/pebble)
- [hello-kubecon example](https://github.com/jnsgruk/hello-kubecon)
- [publish to charmhub](https://juju.is/docs/sdk/publishing)
- [charmcraft upload-resource](https://discourse.charmhub.io/t/charmcrafts-upload-resource-command/4580)
