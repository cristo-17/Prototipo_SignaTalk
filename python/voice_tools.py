import os
import tempfile
import speech_recognition as sr
from playsound3 import playsound


def _normalizar_velocidad(velocidad: str) -> str:
    velocidad = (velocidad or "normal").strip().lower()
    equivalencias = {
        "lento": "lenta",
        "lenta": "lenta",
        "normal": "normal",
        "rapida": "rápida",
        "rápida": "rápida",
        "rapido": "rápida",
        "rápido": "rápida",
    }
    return equivalencias.get(velocidad, "normal")


def _rate_pyttsx3(velocidad: str) -> int:
    return {
        "lenta": 120,
        "normal": 165,
        "rápida": 220,
    }.get(_normalizar_velocidad(velocidad), 165)


def texto_a_voz(text: str, velocidad: str = "normal") -> str:
    """Convierte texto a voz y respeta la velocidad configurada.

    Prioriza pyttsx3 porque permite modificar la velocidad real de reproducción.
    Si pyttsx3 no está instalado, usa gTTS como respaldo.
    """
    if not text or not text.strip():
        return "Por favor ingresa un texto."

    velocidad = _normalizar_velocidad(velocidad)

    # Opción recomendada para presentación: pyttsx3 cambia la velocidad real.
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", _rate_pyttsx3(velocidad))

        # Intenta seleccionar una voz en español si existe en Windows.
        try:
            voices = engine.getProperty("voices")
            for voice in voices:
                nombre = (voice.name or "").lower()
                vid = (voice.id or "").lower()
                langs = " ".join([str(x).lower() for x in getattr(voice, "languages", [])])
                if "spanish" in nombre or "español" in nombre or "es-" in vid or "spanish" in langs or "es" in langs:
                    engine.setProperty("voice", voice.id)
                    break
        except Exception:
            pass

        engine.say(text.strip())
        engine.runAndWait()
        engine.stop()
        return f"Texto reproducido con velocidad {velocidad}."
    except Exception:
        pass

    # Respaldo: gTTS permite modo lento, pero no permite acelerar realmente el audio.
    try:
        from gtts import gTTS

        ruta_audio = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            ruta_audio = tmp.name

        tts = gTTS(text.strip(), lang="es", slow=(velocidad == "lenta"))
        tts.save(ruta_audio)
        playsound(ruta_audio)
        if velocidad == "rápida":
            return "Texto reproducido. Para velocidad rápida real instala pyttsx3."
        return f"Texto reproducido con velocidad {velocidad}."
    except Exception as e:
        return f"Error al reproducir voz: {e}"
    finally:
        try:
            if 'ruta_audio' in locals() and ruta_audio and os.path.exists(ruta_audio):
                os.remove(ruta_audio)
        except PermissionError:
            pass


def voz_a_texto() -> str:
    """Reconoce voz desde el micrófono y devuelve el texto."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            texto = recognizer.recognize_google(audio, language="es-ES")
            return f"Texto reconocido: {texto}"
    except sr.WaitTimeoutError:
        return "No se detectó audio."
    except sr.UnknownValueError:
        return "No se pudo entender el audio."
    except sr.RequestError:
        return "Error al conectar con el servicio de reconocimiento."
    except Exception as e:
        return f"Error de micrófono o reconocimiento: {e}"
