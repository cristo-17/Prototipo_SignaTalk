from gtts import gTTS
from playsound3 import playsound

text = input("Ingresa el texto que quieres escuchar: ")
tts = gTTS(text, lang='es')
tts.save("voz.mp3")
playsound("voz.mp3")