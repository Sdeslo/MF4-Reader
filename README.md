# Plot Browser – MF4 Signal Viewer with DBC Support

**Plot Browser** is a simple graphical tool for visualizing decoded CAN signals from MF4 (ASAM MDF) files using DBC files. It is designed for engineers working with automotive CAN data and lets you quickly view signals, select which to display, and plot them on the same graph or on separate subplots.

---

## 🚀 Features

- Load `.mf4` files recorded from CAN bus tools
- Load `.dbc` files to decode CAN messages into human-readable signals
- Display available decoded signals in a list
- Plot selected signals:
  - All on the same graph, or
  - Each on separate subplots
- Optional dots/markers for each data point
- Automatically labels subplots with signal units from the DBC

---

## 🖥️ Requirements

Python 3.8+  
Install dependencies with:

```bash
pip install asammdf cantools matplotlib
```
---

## How to use

1. Click "Load MF4 File" and select a .mf4 CAN data file.

2. Click "Load DBC File" and select the corresponding .dbc definition.

3. Choose one or more decoded signals from the list.

4. Select plot options:

5. Plot on Same Graph: overlays all signals on one graph.

6. Plot on Subplots: displays each signal in its own subplot.

7. Show Dots on Graph: adds a dot for each data point.

8. Click "Plot Selected Signals" to view the graph(s).

---

## 🛠 Building an Executable

1. Install PyInstaller

```bash
pip install pyinstaller
```
2. Create the executable

```bash
pyinstaller --onefile --windowed name_of_file.py
```
This will generate dist/name_of_file.exe, which you can run on any Windows system (if compiled on windows) — no Python installation required.

---

