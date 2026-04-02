Install
=

Main pre-requisite is the coin-or symphony package. Either install
the prebuilt version, or (as below) install from source.

Doing this with a proxy is awkward. Assuming you have one working ...
```bash
sudo su -
export {http,https,ftp}_proxy='http://127.0.0.1:3128'
apt update
apt upgrade
apt install build-essential git wget libblas3 libblas-dev liblapack3 liblapack-dev gfortran pkg-config
mkdir ~/coinor
cd ~/coinor
wget https://raw.githubusercontent.com/coin-or/coinbrew/master/coinbrew
chmod u+x coinbrew
./coinbrew fetch SYMPHONY
./coinbrew build SYMPHONY --prefix /usr/local
```


Awkward to get multi-threaded version to work
```bash
cd ~/coinor
LDFLAGS='-Wl,--no-as-needed -lgomp -Wl,--as-needed' CC=gcc CXX=g++ \
  ./coinbrew build SYMPHONY --prefix /usr/local --reconfigure --enable-openmp
```
