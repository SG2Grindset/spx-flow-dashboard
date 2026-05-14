from gtts import gTTS

alerts = {
    "a_plus_long.mp3": "Show me the money! A plus long setup detected!",
    "a_plus_short.mp3": "Downside pressure. A plus short setup detected.",
    "b_setup.mp3": "Moderate setup forming. Stay alert.",
    "flow_spike.mp3": "Unusual options activity detected."
}

for filename, text in alerts.items():
    tts = gTTS(text=text, lang='en')
    tts.save(filename)

print("Alert sound pack created.")