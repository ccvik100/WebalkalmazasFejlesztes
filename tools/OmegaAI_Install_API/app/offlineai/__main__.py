"""python -m offlineai indítás. Alapértelmezetten csak localhost."""
import uvicorn
from .core import config, ensure_folders

def main():
    ensure_folders()
    cfg = config()
    uvicorn.run("offlineai.main:app", host=cfg["host"], port=int(cfg["port"]),
                log_level="info", workers=1)

if __name__ == "__main__":
    main()
