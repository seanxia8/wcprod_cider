#FROM nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04
FROM ubuntu:20.04

LABEL maintainer="drinkingkazu"
LABEL contact="contact@deeplearnphysics.org"
LABEL type="cpu"
LABEL version="ub20.04-CIDeR-wcprod"

ARG DEBIAN_FRONTEND=noninteractive

ENV XDG_RUNTIME_DIR=/tmp/$USER

RUN apt-get -y update && \
    apt-get -y install apt-utils && \
    apt-get -y install dpkg-dev g++ gcc binutils git wget curl emacs vim openssh-client krb5-user && \
    apt-get -y install libx11-dev libxpm-dev libxft-dev libxext-dev libssl-dev && \
    apt-get -y install python3-dev python3-tk python3-pip python3-setuptools && \
    apt-get -y install libopenblas-dev libxerces-c-dev libyaml-cpp-dev zsh && \
    apt-get -y install screen tmux && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 --no-cache-dir install -U pip && \
    pip3 --no-cache-dir install --upgrade setuptools numpy pyyaml pytest tqdm pandas plotly jupyter

RUN mkdir /app && cd /app && \
    git clone --no-checkout https://github.com/seanxia8/wcprod_cider.git && \
    cd wcprod_cider && \
    git checkout 1094f089ec77a68b34a3daf018e89c3adc4a9a85 && \
    pip3 --no-cache-dir install .			  

RUN apt-get -y install libspdlog-dev