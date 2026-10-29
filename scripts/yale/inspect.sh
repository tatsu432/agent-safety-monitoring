#!/usr/bin/env bash
set -eu
whoami
hostname -f
pwd
groups
sacctmgr -nP show assoc where user="$(whoami)" format=User,Account,Partition,QOS
sinfo -o '%P | %a | %l | %G | %D'
squeue --me
getquota
