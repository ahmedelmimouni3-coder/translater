import accessible_output3.outputs
speaker=accessible_output3.outputs.auto.Auto()
def speak(text, interrupt=True):
    """Speaks the text through the active screen reader or speech engine."""
    speaker.speak(text, interrupt=interrupt)
