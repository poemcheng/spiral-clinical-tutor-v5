"""Download the official converted Whisper model once; inference stays local."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.speech_input import MODEL_NAME,model_path
from huggingface_hub import snapshot_download
if __name__=='__main__':
    snapshot_download(MODEL_NAME,local_dir=str(model_path()),allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*','preprocessor_config.json'])
    print('Local speech recognition ready: '+str(model_path()))
