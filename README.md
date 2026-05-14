# ishms-rag-app

this is a rag api that was created to serve the ISHMS software.


## REQUIREMENTS
- Python 3.12

### Install Python using Miniconda
1) Download and install mini coda from [here](https://docs.anaconda.com/free/miniconda/#quick-command-line-install)

2) Create a new enviroment using the follwing command:
```bash
$ conda create -n rag-ishms python=3.12
```
3) Activate the enviroment :
```bash
$ conda activate rag-ishms
```

### Install the requires packages 
```bash
$ pip install -r requirements.txt
```

### Run the FastAPI server

```bash         
$ cd ~/rag-ishms/src
```

```bash
$ uvicorn main:app --reload --host 0.0.0.0 --port 5001 
```

### Run Dokcer Compose Service
```bash
$ cd docker
$ cp .env.example .env
```

- update `.env` with your credentials


### for running the drug checker manually
```bash         
$ cd ~/rag-ishms/src
```
```bash         
$ pyhton drug_checker.py
```

### Run the model 
```bash
$ cd ~/llama.cpp/build/bin
```
```bash
$ ./llama-server -m /mnt/g/ishms/modeel/medgemma-4b-it-Q8_0.gguf -ngl 99 --host 0.0.0.0 --port 8080
```

### installing cloudflare to access the server
 -downloading the cloudflare package
```bash
$ wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
```
 - Install it
```bash
$ sudo dpkg -i cloudflared-linux-amd64.deb
```
 - Verify
```bash
$ cloudflared --version
```

### running cloudflare after runnig the depends

```bash
$ cloudflared tunnel run rag-ishms
```
