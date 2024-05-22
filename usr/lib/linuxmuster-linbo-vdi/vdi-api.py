#!/usr/bin/env python3                                                                                                                                                                                                                      
                                                                                                                                                                                                                                            
#########################################################                                                                                                                                                                                   
#                                                                                                                                                                                                                                           
# by Netzint GmbH 2024                                                                                                                                                                                                                      
# Lukas Spitznagel (lukas.spitznagel@netzint.de)                                                                                                                                                                                            
#                                                                                                                                                                                                                                           
#########################################################                                                                                                                                                                                   
                                                                                                                                                                                                                                            
import json                                                                                                                                                                                                                                 
import logging                                                                                                                                                                                                                              
import uvicorn
import os                                                                                                                                                                                                                      
                                                                                                                                                                                                                                            
from fastapi import FastAPI, Request, Response                                                                                                                                                                                            
from subprocess import PIPE, run                                                                                                                                                                                                            
from pydantic import BaseModel
from globalValues import lmnapisecret                                                                                                                                                                                                       
                                                                                                                                                                                                                                            
level = "INFO"

if level == "INFO":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
                        datefmt='%Y-%m-%d:%H:%M:%S',
                        level=logging.INFO)

if level == "DEBUG":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
                        datefmt='%Y-%m-%d:%H:%M:%S',
                        level=logging.INFO)                                                                                                
                                                                                                                                                                                                                                            
app = FastAPI()                                                                                                                                                                                                                             

class ConnectionRequest(BaseModel):
    group: str
    user: str

def __execute(command: list):
  result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
  return result

@app.middleware("http")
async def check_api_key(request: Request, call_next):
    api_secret = request.headers.get('LMN-API-Secret')
    if api_secret != lmnapisecret:
        return Response(content=json.dumps({"detail": "Incorrect API-Secret"}), status_code=401, media_type="application/json")
    response = await call_next(request)
    return response

@app.get("/api/status/clones")
def get_status_of_clones():
    command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getVmStates.py", "-clones" ]
    result = __execute(command)
    if result.returncode == 0:
      return { "status": True, "data": json.loads(result.stdout.encode()) }
    return { "status": False, "data": result.stdout, "error": result.stderr }

@app.get("/api/status/clones/{clone}")
def get_status_of_special_clone(clone: str):
    command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getVmStates.py", clone, "-clones" ]
    result = __execute(command)
    if result.returncode == 0:
      return { "status": True, "data": json.loads(result.stdout.encode()) }
    return { "status": False, "data": result.stdout, "error": result.stderr }

@app.get("/api/status/masters")
def get_status_of_masters():
    command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getVmStates.py", "-master" ]
    result = __execute(command)
    if result.returncode == 0:
      return { "status": True, "data": json.loads(result.stdout.encode()) }
    return { "status": False, "data": result.stdout, "error": result.stderr }

@app.get("/api/status/masters/{master}")
def get_status_of_special_master(master: str):
    command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getVmStates.py", master, "-master" ]
    result = __execute(command)
    if result.returncode == 0:
      return { "status": True, "data": json.loads(result.stdout.encode()) }
    return { "status": False, "data": result.stdout, "error": result.stderr }

@app.post("/api/connection/request")
def request_connection_for_user(data: ConnectionRequest):
    command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getConnection.py", data.group, data.user ]
    result = __execute(command)
    if result.returncode == 0:
      spicedata = json.loads(result.stdout.encode())
      command = [ "/usr/bin/python3", "/usr/lib/linuxmuster-linbo-vdi/getVmStates.py", data.group, "-clones" ]
      result2 = __execute(command)
      if result2.returncode == 0:
        vmdata = json.loads(result2.stdout.encode())
        for vmid in vmdata:
          if vmdata[vmid]["lastConnectionRequestUser"] == data.user:
            return { "status": True, "data": { "ip": vmdata[vmid]["ip"], "configFile": spicedata["configFile"] } }

    return { "status": False, "data": result.stdout, "error": result.stderr }



###############################################################

def main():
    logging.info("Starting Linuxmuster-Linbo-VDI-API on port 5555!")
    uvicorn.run(app, host="0.0.0.0", port=5555)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(e)
