from django.conf import settings
import joblib
import threading

_model = None
_lock = threading.Lock()

def get_model():
    global _model
    if _model is None:
        with _lock:                # thread-safe
            if _model is None:
                _model = joblib.load(settings.ML_MODEL_PATH)
    return _model
