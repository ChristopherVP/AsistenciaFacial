# 📸 Asistencia Facial — Face Recognition Attendance System

**A desktop application that takes class attendance automatically by recognizing students' faces through a webcam. Written in Python (Tkinter + OpenCV), it manages courses and students, runs manual or scheduled roll calls with voice prompts, and writes the results into one Excel sheet per course with automatic attendance percentages.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-blue)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8?logo=opencv&logoColor=white)
![Excel](https://img.shields.io/badge/Reports-Excel%20(.xlsx)-217346?logo=microsoftexcel&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![Status](https://img.shields.io/badge/Status-Educational%20project-green)

Asistencia Facial is a university project that replaces the paper attendance sheet. A teacher creates a **course**, registers each student once with a short **voice-guided face scan**, and from then on the system recognizes the students in front of the camera, marks them present and saves everything into an **Excel file**. Lists can be taken **manually** (press a button) or **automatically** inside a weekly schedule. Everything runs **locally**: no server, no cloud, no database to install.

- **Teachers / users** create a local account, manage their courses, register students, take attendance and open the Excel sheets.
- **Students** only need to look at the camera; no cards, no typing.
- **Recognition** is done on the CPU with two small ONNX models (YuNet for detection, SFace for recognition) that run through OpenCV. Only numeric *face embeddings* are stored — **no photos are saved**.

The code follows a layered design (UI → services/domain → storage), uses immutable data classes, explicit error types and has automated tests for the Excel book, the recognition gallery and the authentication.

---

## Table of Contents

1. [Features at a Glance](#-features-at-a-glance)
2. [How the System Works (Business Rules)](#-how-the-system-works-business-rules)
3. [Project Requirements](#-project-requirements)
4. [Installation and Setup](#-installation-and-setup)
5. [Running the Application](#-running-the-application)
6. [First Start](#-first-start)
7. [Where the Data Is Stored](#-where-the-data-is-stored)
8. [User Guide](#-user-guide)
9. [Recognition Precision](#-recognition-precision)
10. [The Excel Attendance Sheet](#-the-excel-attendance-sheet)
11. [Voice Prompts](#-voice-prompts)
12. [Security and Privacy](#-security-and-privacy)
13. [Validation Rules](#-validation-rules)
14. [Domain Model](#-domain-model)
15. [Configuration Constants](#-configuration-constants)
16. [Project Structure](#-project-structure)
17. [Architecture and Design Notes](#-architecture-and-design-notes)
18. [Running the Tests](#-running-the-tests)
19. [Known Limitations](#-known-limitations)
20. [Troubleshooting](#-troubleshooting)
21. [Author, Repository and License](#-author-repository-and-license)

---

## ✨ Features at a Glance

**Accounts and access**
- The program **always opens on the login screen**. If there are no accounts yet, the user creates one with *“¿No tienes cuenta? Regístrate aquí”*.
- Registration with strict validation: Ecuadorian *cédula* (check digit), full name, unique username, password policy and a **security question** for recovery.
- **Password recovery** through the security question (the answer is stored hashed, never in plain text).
- **Temporary lock** after 5 wrong passwords.
- **“Save user” prompt** in the style of Google Chrome: a small card that slides down from the top after login (*Save / Not now*). It never blocks the program. Saved users can enter with **one click** next time.

**Courses and students**
- Create, rename and delete **courses**; each course has its own students, schedule and Excel file.
- **Student registration with a guided face scan**: consent checkbox, voice instructions, live progress bar, frontal-face check and **duplicate-face detection across all courses**.
- Students are always listed **A–Z by surname**.

**Taking attendance**
- **Manual roll call:** press *Iniciar lista*; a **stopwatch** starts from `00:00` and the camera stays on until you press *Finalizar y guardar*.
- **Automatic roll call:** define weekly intervals (days + start/end time); when the time comes the list starts by itself, a voice announces it, a warning is spoken one minute before the end, and the list is saved when the interval ends.
- **Auto-finish:** as soon as **every student** of the course is present the list is saved and finished automatically, and a voice says *“Lista guardada. Todos los estudiantes han asistido.”*
- Live camera view with boxes and names, live roster (*Presente / Sin registrar*) and counters (present / unregistered / total).

**Recognition quality**
- Three **precision levels** (Flexible, Equilibrado, Estricto) that really change the similarity threshold, the ambiguity margin between two students and the number of confirmation frames.
- Multi-frame confirmation: a student is marked only after being recognized in several consecutive frames.

**Cameras**
- Cameras are listed **by their real name, like Windows Device Manager** (for example *HP TrueVision HD Camera*), with a **Test camera** button and an *IN USE* marker for the selected one.
- **The camera is never turned on by itself**: it only opens when you test it, register a student or take a list.

**Excel output**
- One `.xlsx` per course: ID, name, **attendance % (live Excel formula)** and one column per list (`1` = present, `0` = absent) with date and time.
- Automatic CSV backup if the Excel file cannot be written.

**Polish**
- Splash screen with progress, generated vector logo and window icon (no image files needed), maximized responsive window, scrollable tabs, validated inputs (letters only in names, digits only in ID/time fields).

---

## 📐 How the System Works (Business Rules)

### Roll call life cycle

```
Idle ──► Camera opens ──► Recognizing (stopwatch / countdown) ──► Finalize ──► Saved in Excel
                                   │                                   ▲
                                   └── all students present ───────────┘ (automatic save + voice)
```

| Mode | Starts when | Timer | Ends when |
|------|-------------|-------|-----------|
| **Manual** | You press *▶ Iniciar lista* | **Stopwatch** counting up from `00:00` (no estimated time) | You press *■ Finalizar y guardar*, or every student is present |
| **Automatic** | The clock enters a schedule interval of an enabled course | **Countdown** to the end of the interval | The interval ends, you press *Finalizar y guardar*, or every student is present |

Rules that apply to both:
- Only **one list can run at a time**. While a list is running you cannot change courses, students or schedules.
- A list needs a course with **at least one registered student**.
- On start, the system adds a **new column** to the Excel file with all students set to `0` (absent). Students recognized during the list are changed to `1` when the list is finalized.
- If you log out or close the program during a list, it asks whether to **finish and save** first.
- If the camera stops delivering images (about 90 consecutive failed reads) the list is ended safely and the data already recognized is kept.

### Automatic schedule rules
- A schedule slot has **one or more weekdays**, a **start time** and an **end time** (`HH:MM`, 24 h). The end must be after the start and inside the same day.
- A course must have **at least one slot** and the **automatic list switch enabled** (*AUTOMÁTICA ACTIVA*).
- Each course starts its automatic list **at most once per day** (`last_auto_date` is saved), even if you close and reopen the program inside the interval.
- When an automatic list starts, the window is brought to the front and the camera turns on. **The program must be open (logged in) for automatic lists to run.** If you open it in the middle of an interval, the list starts then and ends at the interval’s end.
- If the course has no students, the automatic list is skipped and a notice is shown.

### Recognition rules
1. The camera frame is analyzed by the **YuNet** detector (every second frame, for speed).
2. Each detected face is aligned and converted into a **128-number embedding** by the **SFace** recognizer.
3. The embedding is compared (cosine similarity) with every stored embedding of the course’s students. Each student is scored by his **best sample**.
4. The best student is accepted only if **(a)** the score reaches the **threshold** and **(b)** he beats the **second-best student by the required margin** (otherwise the face is “ambiguous” and shown as *Desconocido*).
5. The student is marked present only after being recognized in **N consecutive processed frames** (`confirm_frames`). Switching between two people resets the counter.

### Student enrollment rules
1. Enter a valid cédula and the student’s full name; tick the **consent** checkbox.
2. Press *Iniciar escaneo facial*. A voice asks the student to come closer and look at the camera.
3. The scan needs **exactly one face**, with a detector confidence ≥ 0.90, looking **frontally** (limited head turn and tilt).
4. **5 samples** are taken, at least 0.6 s apart. A reminder is spoken after 8 s of inactivity. The scan fails after **60 s**.
5. Before saving, the face is compared with **every student of every course**; if it already exists (even with another cédula) the registration is **rejected** with a voice message. This prevents the same person from being registered twice.
6. The student is saved in the course and added to the Excel sheet. If the Excel file is open elsewhere the student is still saved and will be added to the sheet automatically at the next list.

---

## 📋 Project Requirements

### Functional requirements

| ID | Requirement |
|----|-------------|
| FR-01 | Create a local user account (cédula, name, username, password, security question) and log in with username and password; login is always the first screen. |
| FR-02 | Recover a forgotten password through the account’s security question. |
| FR-03 | Offer a non-blocking “save user” prompt and allow one-click login for saved users (switchable in *Ajustes*). |
| FR-04 | Create, rename and delete courses. |
| FR-05 | Register students with cédula, name, consent and a guided face scan (5 frontal samples). |
| FR-06 | Reject duplicate cédulas inside a course and duplicate faces across all courses. |
| FR-07 | Take attendance manually, with a stopwatch, until the user finishes and saves. |
| FR-08 | Take attendance automatically inside weekly schedule intervals, once per course per day. |
| FR-09 | Finish and save the list automatically when all students are present. |
| FR-10 | Recognize several faces at the same time and show name or *Desconocido* on the live video. |
| FR-11 | Let the user choose the recognition precision (Flexible / Equilibrado / Estricto). |
| FR-12 | List the available cameras by their Device Manager name, test each one and save the chosen camera. |
| FR-13 | Save every list in the course’s Excel file with date/time column and an attendance-percentage formula. |
| FR-14 | Write a CSV backup when the Excel file cannot be saved. |
| FR-15 | Speak the key events with a Spanish voice (scan guidance, automatic list start, one-minute warning, list saved). |
| FR-16 | Validate every input at the boundary: digits only for cédula, letters for names, hours 0–23 and minutes 0–59. |

### Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Desktop GUI** built with Python’s Tkinter / ttk. |
| NFR-02 | **Fully local and offline** after the first start (models are downloaded once). No server, no cloud, no database engine. |
| NFR-03 | **Privacy:** no photos are stored, only face embeddings; passwords and security answers are salted and hashed (PBKDF2-HMAC-SHA256). |
| NFR-04 | **No secrets in the code.** There are no keys, tokens or credentials in the project. |
| NFR-05 | **Atomic writes:** JSON files are written to a temporary file and then replaced, so a crash never leaves a half-written file. |
| NFR-06 | **Responsive UI:** recognition runs every second frame, the video is drawn at ~30 FPS, and long operations show progress. |
| NFR-07 | **Immutable data classes** and explicit error types (`ValidationError`, `CameraError`, `AuthError`…); errors are reported to the user, never silently ignored. |
| NFR-08 | **Language:** the user interface and voice prompts are in **Spanish**. |
| NFR-09 | **Automated tests** with `pytest` for the Excel book, the face gallery and authentication. |

### Software requirements

| Requirement | Details |
|-------------|---------|
| **Operating system** | **Windows 10 / 11** (main target: DirectShow cameras, Windows speech voice, PowerShell, *Segoe UI* font). Linux/macOS can run the core but without voice and without camera names. |
| **Python** | **Python 3.10 or newer** (3.11 and 3.13 were used for development). Must include **Tkinter** (the official installer from python.org includes it). |
| **`opencv-python`** | ≥ 4.8 — provides `FaceDetectorYN` and `FaceRecognizerSF`. |
| **`numpy`** | ≥ 1.24 — vector math for embeddings. |
| **`openpyxl`** | ≥ 3.1 — reads and writes the Excel files. |
| **`pillow`** | ≥ 10.1 — logo, icon and text drawn on the video. |
| **`pygrabber`** | ≥ 0.2, **Windows only** — exact DirectShow camera names (optional but recommended). |
| **`pytest`** | Only to run the tests (not in `requirements.txt`). |
| **PowerShell** | Included with Windows. Used to read the camera names from Device Manager and to speak with the Windows voice. |
| **Spanish voice** *(optional)* | A Spanish text-to-speech voice (es-MX, es-ES or es-US) installed in Windows. Without it the program works but is silent. |
| **Internet** | Needed **only on the first start** to download the two ONNX models (see [First Start](#-first-start)). |

### Hardware requirements

| Requirement | Details |
|-------------|---------|
| **Webcam** | Any USB or integrated camera that Windows lists in Device Manager under *Cameras*. |
| **CPU / RAM** | Any modern 64-bit CPU, 4 GB RAM or more. **No GPU needed.** |
| **Display** | At least 1100 × 600 px recommended (the main window opens maximized, minimum 1100 × 520). |
| **Light** | A well-lit, front-facing scene gives much better recognition. |
| **Disk** | About 100 MB free (models + courses + Excel files). |

---

## 🔧 Installation and Setup

```bash
# 1. Clone the repository
git clone https://github.com/ChristopherVP/AsistenciaFacial.git
cd AsistenciaFacial
```

### 1. Install Python
Download Python 3.10+ from <https://www.python.org/downloads/> and, in the installer, tick **“Add python.exe to PATH”**. Check it:

```bash
python --version
python -c "import tkinter; print('Tkinter OK')"
```

### 2. Create a virtual environment (recommended)

```bat
:: Windows
python -m venv .venv
.venv\Scripts\activate
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt`:

```text
opencv-python>=4.8
numpy>=1.24
openpyxl>=3.1
pillow>=10.1
pygrabber>=0.2; sys_platform == "win32"
```

> 💡 `pygrabber` is installed automatically on Windows. If you skip it, the program still works: it reads the camera names from Windows Device Manager through PowerShell instead.

### 4. Check the camera and permissions
1. Open Windows **Settings → Privacy & security → Camera** and make sure **camera access** and **“Let desktop apps access your camera”** are **On**.
2. Close any other program that uses the camera (Zoom, Teams, browser tabs, the Camera app).

There is nothing else to configure: no database, no environment variables and no credentials.

---

## ▶️ Running the Application

From the project root (with the virtual environment active):

```bash
python main.py
```

What `main.py` does, in order:
1. Registers the Windows app identity (so the taskbar shows the app icon).
2. Creates the Tk root, applies the theme and installs the generated icon.
3. Shows a **splash screen** while it loads courses, settings and users, and prepares the **face models** (downloading them if missing).
4. Opens the **login window**. After a successful login it opens the **main window** (Take attendance / Courses / Settings).
5. On *Cerrar sesión* it returns to the login; on closing the window the program exits.

Optional: to launch it without a console window on Windows, run it with `pythonw main.py` or create a shortcut to `pythonw.exe main.py`.

---

## 🌱 First Start

On the very first run:

1. **Models download.** The splash shows *“Descargando modelo de reconocimiento (solo la primera vez)…”*. Two ONNX files are downloaded from the official OpenCV Zoo on GitHub into `~/AsistenciaFacial/modelos/`:

   | File | Purpose |
   |------|---------|
   | `face_detection_yunet_2023mar.onnx` | Face **detector** (YuNet) |
   | `face_recognition_sface_2021dec.onnx` | Face **recognizer** (SFace, 128-dimension embeddings) |

   The downloads are written to a temporary file first and verified (minimum size) before being used. If you have **no internet access**, download both files manually from the OpenCV Zoo ([YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)) and copy them into the `modelos` folder; the program then starts offline.
2. **Data folder.** `~/AsistenciaFacial/` (for example `C:\Users\<you>\AsistenciaFacial\`) is created as needed.
3. **Login screen.** There are no accounts yet, so click **“¿No tienes cuenta? Regístrate aquí”**, create your account (see the [User Guide](#-user-guide)) and then sign in.
4. **Create your first course** in the *Cursos* tab, register students and take your first list.

---

## 💾 Where the Data Is Stored

Everything lives in one folder in your user profile — nothing is written inside the project folder:

```text
C:\Users\<you>\AsistenciaFacial\
├── modelos\                          # Downloaded ONNX models (YuNet + SFace)
├── cursos\
│   └── <course-slug>-<id>\
│       ├── curso.json                # Course: students (embeddings), schedule, settings
│       └── <Course name>_ListaAsistencia.xlsx   # Attendance sheet (default location)
├── respaldos\                        # CSV backups when the Excel could not be saved
├── ajustes.json                      # Camera and precision settings
├── usuarios.json                     # Local accounts (salted password hashes)
└── icono.ico                         # Generated application icon
```

| File | Content |
|------|---------|
| `curso.json` | Course id and name, Excel path, **students** (`student_id`, `name`, 5 embeddings of 128 numbers each), **schedule slots**, automatic-list switch and last automatic date. |
| `ajustes.json` | `camera_index`, `camera_name`, `threshold` (the precision level). |
| `usuarios.json` | For each user: cédula, name, username, PBKDF2 salt + hash of the password, security question, salt + hash of the answer, “remembered” flag. **Never the plain password.** |
| `*_ListaAsistencia.xlsx` | The attendance sheet (see [below](#-the-excel-attendance-sheet)). You can change its location per course with **Cambiar…** in *Cursos*. |
| `*.corrupto` | If `usuarios.json` cannot be read it is renamed to `usuarios.corrupto` and the user is warned, so nothing is lost silently. |

To **back up** the system copy the whole `AsistenciaFacial` folder. To **reset** it, close the program and delete the folder (the models will be downloaded again).

---

## 🧭 User Guide

### 1. Create your account and sign in
1. On the login screen click **¿No tienes cuenta? Regístrate aquí**.
2. Fill in: **cédula** (10 digits, validated), **full name** (letters only, surname first), **username** (4–20 chars), **password** (8–64 chars, typed twice) and a **security question + answer**.
3. Go back to the login screen, enter your username and password and press **Ingresar**. Use *👁 Mostrar contraseña* to see what you type.
4. After login a card slides down from the top: **“¿Guardar usuario?”**. Press **Guardar** to enter with one click next time, or **Ahora no** (it disappears by itself after 15 s). You can change this later in *Ajustes → Mi cuenta*.
5. Forgot your password? Click **¿Olvidaste tu contraseña?**, type your username, answer your security question and choose a new password.

### 2. Settings (*⚙ Ajustes*) — do this first
- **📷 Cámara del sistema:** the cameras appear with their Device Manager name (e.g. *HP TrueVision HD Camera*). Press **▶ Probar cámara** to see live which one is recording **before** choosing it, pick the one you want (it shows **✔ EN USO**) and press **💾 Guardar ajustes**. Use *Buscar cámaras* after plugging in a new one. *The camera only turns on while you are testing.*
- **🎯 Precisión del reconocimiento:** choose *Flexible*, *Equilibrado* (default) or *Estricto* (see [Recognition Precision](#-recognition-precision)).
- **👤 Mi cuenta:** switch **“Entrar con un clic”** on or off.

### 3. Courses (*📚 Cursos*)
1. **➕ Nuevo curso** — type the course name (unique, up to 60 characters). **✏ Renombrar** and **🗑 Eliminar curso** are next to it. Deleting a course removes its students and schedule from the program; the Excel file is left on disk.
2. **📊 Archivo de asistencia (Excel):** *Abrir* opens the sheet; *Cambiar…* lets you choose another file.
3. **👥 Estudiantes:** press **➕ Agregar estudiante**:
   1. Type the **cédula** (only digits are accepted; the field says *✔ Cédula válida* when correct) and the **full name**.
   2. Tick the **consent** box (*“El estudiante autoriza el uso de su rostro…”*).
   3. Press **🔒 Iniciar escaneo facial**. The voice says *“Acerque su cara a la cámara, por favor.”* The student looks straight at the camera until the progress bar reaches 100 % and the voice says *“Rostro registrado.”*
   4. A green **“Registro confirmado”** summary appears.
   Use **Quitar seleccionado** to remove a student (asks for confirmation).
4. **⏰ Horario de lista automática:** press **➕ Agregar horario**, choose the **weekdays**, the **start** and **end** time (hours 0–23, minutes 0–59 — other characters cannot be typed) or use the quick buttons *10 / 20 / 30 / 45 min*, and save. Then switch the automatic list **on** for the course. The tag changes to **AUTOMÁTICA ACTIVA**.

### 4. Take attendance (*📷 Tomar lista*)
**Manual**
1. Choose the **course** in the drop-down.
2. Press **▶ Iniciar lista**. The camera turns on and the **stopwatch starts at 00:00**.
3. Students look at the camera one by one (or together). Each recognized student turns to **Presente** with the time, and a green box with the name appears on the video.
4. Press **■ Finalizar y guardar** when you are done — or let the program finish by itself when everybody is present. The camera turns off and the Excel file is updated.

**Automatic**
1. Enable the schedule in the course (see above) and **leave the program open and logged in**.
2. When the interval begins the window comes to the front, a voice says *“La lista de <course> va a empezar. Acérquese a la cámara para registrarse.”* and the list starts with a **countdown**.
3. One minute before the end the voice says *“Queda un minuto para finalizar la lista.”*
4. At the end of the interval (or when all students are present) the list is saved.

At the top of the panel you always see the **next automatic list** (*“Próxima lista automática: Infra2 · Lun 23/11 de 19:00 a 19:20”*) or *“Sin listas automáticas programadas”*.

After a list is saved, the table shows **Presente / Falta** for every student and the counters show the final numbers of that list.

---

## 🎯 Recognition Precision

The three levels in *Ajustes* are real: each one sets **three parameters** of the recognition engine.

| Level | Similarity threshold | Ambiguity margin | Confirmation frames | When to use it |
|-------|:--------------------:|:----------------:|:-------------------:|----------------|
| **Flexible** | 0.33 | 0.00 | 2 | The system does not recognize students easily (poor light, glasses, camera far away). |
| **Equilibrado** *(default)* | 0.40 | 0.05 | 3 | Recommended for most cases. |
| **Estricto** | 0.50 | 0.10 | 5 | There are false registrations or look-alike students; avoids confusing one person with another. |

- **Similarity threshold:** minimum cosine similarity between the live face and the stored face.
- **Ambiguity margin:** the best student must beat the second-best student by at least this value; otherwise the face is shown as *Desconocido* and nobody is marked.
- **Confirmation frames:** how many consecutive processed frames must recognize the same student before he is marked present.

Only the threshold is saved in `ajustes.json`; the margin and the frames are derived from the closest level. The threshold is also used when registering a student to detect an existing duplicate face.

---

## 📊 The Excel Attendance Sheet

One workbook per course, named `<Course name>_ListaAsistencia.xlsx`:

| Cédula | Apellidos y nombres | % Asistencia | 19/11/2026 15:30 | 20/11/2026 07:00 | … |
|--------|---------------------|:------------:|:----------------:|:----------------:|---|
| 1712345678 | PÉREZ GÓMEZ JUAN | 100 % | 1 | 1 | |
| 1798765432 | VILLÓN PERALTA ANA | 50 % | 1 | 0 | |

- **Column C — `% Asistencia`** is a live Excel formula: `=IF(COUNT(D2:XFD2)=0,"",SUM(D2:XFD2)/COUNT(D2:XFD2))`.
- **One new column per list**, with the date and time of the start in the header (`DD/MM/YYYY HH:MM`). `1` = present, `0` = absent.
- A student registered **after** a list was taken has an **empty** cell for it, so older lists **never count against** him in the percentage.
- Students are **sorted A–Z** by surname (accents ignored) and the header row and first columns are frozen.
- When a list starts every student of the course is written as `0`; the final `1`s are written when the list is finalized.
- **The Excel file must be closed** while a list is being saved. If it is open in Excel the program shows *“El Excel está abierto en otro programa. Ciérralo y vuelve a intentar.”* with a **Retry / Cancel** dialog. If you cancel, the result is written to `~/AsistenciaFacial/respaldos/lista_<course>_<date>.csv` so no attendance is lost.
- Older workbooks (before the percentage column existed) are **migrated automatically** without losing any date column.

---

## 🔊 Voice Prompts

The program speaks (in Spanish) using the **Windows text-to-speech engine** through PowerShell, without freezing the window. The voice tries the cultures `es-MX`, `es-ES` and `es-US`.

| Moment | Spoken text |
|--------|-------------|
| Start of the face scan | *“Acerque su cara a la cámara, por favor.”* |
| Student not looking at the camera | *“Por favor, mire fijamente a la cámara.”* |
| Face registered | *“Rostro registrado.”* |
| Face already registered | *“Este rostro ya está registrado. No se creó un registro nuevo.”* |
| Scan failed or timed out | *“No se pudo registrar el rostro. Intente de nuevo.”* |
| Automatic list starts | *“La lista de <course> va a empezar. Acérquese a la cámara para registrarse.”* |
| One minute before the end of an automatic list | *“Queda un minuto para finalizar la lista.”* |
| All students present and the list was saved | *“Lista guardada. Todos los estudiantes han asistido.”* |

If the PC has no Spanish voice (or is not Windows) the program keeps working and shows on-screen messages instead.

---

## 🔐 Security and Privacy

| Area | Implementation |
|------|----------------|
| **Password hashing** | **PBKDF2-HMAC-SHA256**, 200 000 iterations, random 16-byte salt per secret (Python standard library only). The security answer is hashed the same way (lower-cased, without accents). |
| **Constant-time check** | Hashes are compared with `hmac.compare_digest`. |
| **Login throttling** | After **5 failed attempts** the username is locked for **30 seconds**. The same limit applies to password recovery. Messages never reveal whether the username or the password was wrong (*“Usuario o contraseña incorrecta.”*). The counter lives in memory. |
| **Biometric data** | Only **128-number face embeddings** are stored (5 per student). **No photos or video are saved.** They stay in the local folder `~/AsistenciaFacial/cursos/`. |
| **Consent** | A student cannot be registered unless the **consent checkbox** is ticked. |
| **No secrets in code** | There are no API keys, passwords or tokens. The program makes no network call except the one-time model download. |
| **Atomic writes** | JSON files are written to `*.tmp` and replaced, preventing corruption on power loss. |
| **Corrupt files** | A damaged `usuarios.json` is moved to `usuarios.corrupto` and the user is warned. A damaged course folder is skipped with a warning instead of crashing. |
| **Input validation** | Entry fields only accept valid characters (digits for cédula, letters for names, 0–23 / 0–59 for time), and every value is validated again before it is saved. |

> ⚠️ Face data is **sensitive personal data**. Use the system with the students’ consent, keep the `AsistenciaFacial` folder protected, and follow your institution’s and country’s data-protection rules (for example Ecuador’s *Ley Orgánica de Protección de Datos Personales*).

---

## ✅ Validation Rules

| Field | Rule |
|-------|------|
| **Cédula** | Exactly **10 digits**, numeric only (letters cannot be typed); province **01–24**; third digit **0–5**; valid **modulus-10 check digit**. Unique per user account and per course. |
| **Full name** | Letters (with accents and ñ) and single spaces only; **at least two words**; up to 60 characters; stored in **UPPERCASE**; surname first. |
| **Username** | 4–20 characters, starts with a letter, then letters, digits, dot or underscore; stored in lowercase; unique. |
| **Password** | 8–64 characters; must be typed twice and match. |
| **Security question** | Must be one of the 5 predefined questions; the answer needs at least 3 characters. |
| **Course name** | Not empty, up to 60 characters, unique (case-insensitive). |
| **Schedule time** | Hours **0–23** and minutes **0–59** (only digits can be typed, padded to two digits); end time later than start time, same day. |
| **Schedule days** | At least one weekday; the same slot cannot be added twice. |
| **Student** | Consent required; one face in view, frontal, confidence ≥ 0.90; face not already registered in any course. |
| **Excel file** | Must be a valid `.xlsx` that is not locked by another program. |

---

## 🧩 Domain Model

All models are **immutable dataclasses** (`frozen=True`); “changing” one returns a new object.

| Class | Responsibility |
|-------|----------------|
| `User` | Account: cédula, full name, username, password salt/hash, security question, answer salt/hash, iterations and *remembered* flag. |
| `Student` | Cédula (`student_id`), name and the tuple of face **embeddings**. |
| `Slot` | Weekly interval: weekdays + `HH:MM` start and end. Knows if a moment is inside it and its duration. |
| `Course` | Id, name, Excel path, students, slots, automatic-list switch and last automatic date. Adds/removes students and slots returning a new course. |
| `AppSettings` | Selected camera (index and name) and recognition threshold. |
| `CameraInfo` | Index, real name, kind (integrated / unknown) and availability. |
| `FaceResult` | Box, label and whether the face was recognized (drawn on the video). |
| `RecordResult` | Column letter, present count and total after a list is saved. |
| `PrecisionLevel` | Name, threshold, ambiguity margin, confirmation frames and description. |

**Services**

| Class / module | Responsibility |
|----------------|----------------|
| `FaceEngine` | Downloads/loads the models, **detects** faces (YuNet) and computes **embeddings** (SFace). |
| `Gallery` | Matrix of the course’s embeddings; `identify()` (threshold + margin per student) and `best_match()` (duplicate detection). |
| `AttendanceSession` | Processes frames, counts consecutive recognitions per student and emits *registered* / *already* events. |
| `AttendanceBook` | Reads/writes the Excel workbook: start a list, finalize, sync students, sort A–Z, percentage formula, migration. |
| `FaceEnrollment` | State machine of the face scan (samples, frontal check, reminders, timeout). |
| `Camera` / `detect_cameras` / `device_names` | OpenCV capture (DirectShow on Windows), real camera names, frame rendering with boxes and overlays. |
| `UserRepository` / `LoginThrottle` | Accounts, hashing, login, recovery, remembered users and lock-out. |
| `CourseRepository` / `SettingsRepository` | JSON persistence with atomic writes and course folders. |
| `Speaker` | Non-blocking Spanish speech through Windows PowerShell. |
| `scheduler` | Finds courses whose interval is active now and describes the next automatic list. |
| `validators` | All input rules (cédula, names, usernames, passwords, hours and minutes). |

---

## ⚙️ Configuration Constants

All tunable values are in `asistencia/config.py`:

| Constant | Default | Meaning |
|----------|---------|---------|
| `DATA_DIR` | `~/AsistenciaFacial` | Root folder of all data. |
| `CONFIRM_FRAMES` | 3 | Default consecutive frames to confirm a student. |
| `PROCESS_EVERY_N_FRAMES` | 2 | Recognition runs every N-th frame. |
| `FRAME_DELAY_MS` | 33 | Video refresh (~30 FPS). |
| `MAX_READ_FAILURES` | 90 | Failed reads before a list is ended. |
| `VIEW_WIDTH` × `VIEW_HEIGHT` | 640 × 480 | Camera resolution requested. |
| `MAX_SAMPLES` | 5 | Face samples per student. |
| `SAMPLE_INTERVAL` | 0.6 s | Minimum time between samples. |
| `MIN_FACE_SCORE` | 0.90 | Detector confidence required to enroll. |
| `MAX_YAW_RATIO` / `MAX_ROLL_RATIO` | 0.25 / 0.30 | Allowed head turn / tilt for the frontal check. |
| `SCAN_TIMEOUT_SECONDS` | 60 | Face scan time limit. |
| `REMIND_SECONDS` | 8 | Inactivity before the voice reminder. |
| `PBKDF2_ITERATIONS` | 200 000 | Hash cost. |
| `MAX_LOGIN_ATTEMPTS` / `LOCKOUT_SECONDS` | 5 / 30 | Lock-out policy. |
| `MIN/MAX_USERNAME_LENGTH` | 4 / 20 | Username length. |
| `MIN/MAX_PASSWORD_LENGTH` | 8 / 64 | Password length. |

---

## 🧱 Project Structure

```text
AsistenciaFacial/
├── main.py                          # Entry point: splash, models, login loop, main window
├── requirements.txt                 # Python dependencies
├── tests/
│   ├── test_asistencia.py           # Excel book, gallery, duplicate faces, snapshots
│   └── test_auth.py                 # Registration, login, lock-out, recovery, remembered users
└── asistencia/
    ├── config.py                    # Paths, thresholds, precision levels, colors, constants
    ├── models.py                    # Immutable dataclasses (Student, Course, Slot, settings…)
    ├── errors.py                    # AppError, ValidationError, CameraError, AuthError…
    ├── validators.py                # Input rules: cédula, name, username, password, hour/minute
    ├── auth.py                      # Users, PBKDF2 hashing, login throttle, recovery
    ├── storage.py                   # Atomic JSON; course and settings repositories
    ├── face_engine.py               # Model download, YuNet detector, SFace embeddings, Gallery
    ├── enrollment.py                # Guided face-scan state machine
    ├── attendance.py                # AttendanceSession (live) + AttendanceBook (Excel)
    ├── scheduler.py                 # Automatic-list schedule logic
    ├── camera.py                    # Camera capture, real device names, frame rendering
    ├── voice.py                     # Windows text-to-speech (non-blocking)
    ├── branding.py                  # Generated logo, window icon, splash screen
    ├── liveness.py                  # Experimental eye-openness helper (not used yet)
    └── ui/
        ├── login_window.py          # Login, register and password recovery
        ├── main_window.py           # Header, tabs, clock, “save user” prompt trigger
        ├── attendance_tab.py        # Take attendance: live camera, roster, timer, voices
        ├── courses_tab.py           # Courses, students, schedule, Excel path
        ├── settings_tab.py          # Camera, precision, account
        ├── dialogs.py               # Student registration, schedule and name dialogs
        ├── save_prompt.py           # Non-blocking “¿Guardar usuario?” card (slides from top)
        ├── camera_preview.py        # Live camera test
        ├── widgets.py               # Cards, chips, steppers, camera view, tables
        ├── theme.py                 # ttk theme and styles
        ├── state.py                 # Shared application state
        ├── scrollable.py            # Scrollable tab container
        └── window_utils.py          # Window helpers (maximize)
```

---

## 🏗 Architecture and Design Notes

- **Layers:** `ui` (Tkinter) → services (`attendance`, `enrollment`, `face_engine`, `scheduler`, `auth`) → `storage` (JSON / Excel). The UI never touches files directly.
- **Shared state:** `AppState` holds the engine, repositories, settings and current user, and notifies tabs when courses change.
- **Immutability:** dataclasses are frozen; `Course.add_student()` returns a new `Course`, and `AttendanceSession` replaces its dictionaries instead of mutating them.
- **Single responsibility:** each module does one thing (`validators` only validates, `scheduler` only decides *when*, `AttendanceBook` only reads/writes Excel).
- **Explicit errors:** typed exceptions are raised at the boundary and shown to the user; fallbacks (for example the PowerShell camera names) are documented in the code.
- **Responsiveness:** recognition is limited to every second frame, camera names are read without opening the cameras, and speech runs in a separate process.
- **The camera is opened only when needed:** testing, enrolling a student or running a list. Listing cameras never turns the camera light on.
- **Testability:** clocks are injectable (`LoginThrottle`, `FaceEnrollment`, `UserRepository`), so time-dependent logic is tested without waiting.

---

## 🧪 Running the Tests

```bash
python -m pip install pytest
python -m pytest -q tests
```

The tests cover the Excel book (percentage formula, migration of old files, per-course roster), the recognition gallery (duplicates, empty gallery), and authentication (hashing, validation, lock-out and unlock, recovery, remembered users, corrupt file, legacy accounts).

---

## ⚠️ Known Limitations

This is an **educational project**, not a certified proctoring or payroll system.

- **No anti-spoofing (liveness) check:** a high-quality photo or video of a registered student shown to the camera could be recognized. Supervise the roll call. An experimental eye-openness helper (`liveness.py`) exists but is **not connected** yet.
- **Recognition depends on light and camera quality.** Twins or very similar faces can be confused; use *Estricto* in that case.
- **Automatic lists only run while the program is open and logged in** on the PC.
- **“Entrar con un clic” has no password prompt** for saved users: anyone with access to the logged-in Windows session can enter. Turn it off on shared computers.
- **The login lock-out is kept in memory** and resets when the program restarts.
- **Local only:** there is no network sync, no multi-computer database and no user roles; every account sees the courses stored on that PC.
- **Windows-first:** voice, exact camera names and the Windows identity/taskbar icon are Windows features.
- **Excel is the only export format** (a CSV is written only as an emergency backup).
- **Spanish only:** the interface and voice prompts are in Spanish.

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| `No se pudo descargar el modelo …` at start-up | Check your internet connection or download the two `.onnx` files manually (links in [First Start](#-first-start)) and put them in `~/AsistenciaFacial/modelos/`. |
| `ModuleNotFoundError: No module named 'cv2'` (or `numpy`, `openpyxl`, `PIL`) | Activate the virtual environment and run `python -m pip install -r requirements.txt`. |
| `ModuleNotFoundError: No module named 'tkinter'` | Reinstall Python from python.org (keep *tcl/tk* checked). On Linux: `sudo apt install python3-tk`. |
| `AttributeError: module 'cv2' has no attribute 'FaceDetectorYN'` | Your OpenCV is too old: `python -m pip install --upgrade "opencv-python>=4.8"`. |
| `No se pudo abrir la cámara` | Close other apps using the camera and enable **Settings → Privacy & security → Camera**. Then press *Buscar cámaras* in *Ajustes*. |
| Cameras show as *Cámara 0*, *Cámara 1* | Run `python -m pip install pygrabber` (Windows) so the exact DirectShow names are used. |
| The camera turns on by itself when I open the program | It only happens if a course has an **active automatic schedule** and you open the program inside that interval. Otherwise the camera is never opened without your action. |
| Students are not recognized | Improve the light, face the camera, and switch *Precisión* to **Flexible**. Re-register the student in good light if the problem persists. |
| Wrong student is marked | Switch *Precisión* to **Estricto** and re-register look-alike students with better light. |
| *El Excel está abierto en otro programa* | Close the `.xlsx` in Excel and press **Retry**. If you cancel, find the CSV backup in `~/AsistenciaFacial/respaldos/`. |
| No voice is heard | Check the volume and that Windows has a Spanish voice installed (*Settings → Time & language → Speech*). The program works without voice. |
| *Demasiados intentos fallidos. Espere N s* | Wait 30 seconds (it applies to the username after 5 failed attempts) or use *¿Olvidaste tu contraseña?*. |
| *No se pudo leer el archivo de usuarios* | The file was damaged; a copy was saved as `usuarios.corrupto`. Create your account again. |
| The window is too small / cut off | The window needs at least 1100 × 520 px; reduce Windows display scaling or use a larger screen. |
| Reset everything | Close the program and delete `~/AsistenciaFacial/` (models will be downloaded again). |

---

## 👤 Author, Repository and License

- **Author:** Christopher Josué Villón Peralta — Systems Engineering student, Universidad Central del Ecuador
- **Repository:** <https://github.com/ChristopherVP/AsistenciaFacial>
- **Context:** university project.
- **Models:** [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) and [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) from the OpenCV Zoo (each under its own license).
- **License:** *not specified yet* — add a `LICENSE` file (for example MIT) if you want others to reuse the code.
