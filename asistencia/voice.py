from __future__ import annotations

import os
import subprocess
import sys

SCRIPT = (
    "Add-Type -AssemblyName System.Speech;"
    "$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "foreach ($cultura in 'es-MX','es-ES','es-US') {"
    " try { $voz.SelectVoiceByHints("
    "[System.Speech.Synthesis.VoiceGender]::NotSet,"
    "[System.Speech.Synthesis.VoiceAge]::NotSet, 0,"
    "[System.Globalization.CultureInfo]::GetCultureInfo($cultura)); break } catch { } };"
    "$voz.Speak($env:ASISTENCIA_TEXTO)"
)


class Speaker:
    def __init__(self) -> None:
        self._available = sys.platform.startswith("win")
        self._process: subprocess.Popen | None = None

    @property
    def available(self) -> bool:
        return self._available

    def speak(self, text: str) -> bool:
        if not self._available:
            return False
        self.stop()
        environment = {**os.environ, "ASISTENCIA_TEXTO": text}
        try:
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            self._available = False
            return False
        return True

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None
