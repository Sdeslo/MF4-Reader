import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, MULTIPLE
from asammdf import MDF
import cantools
import matplotlib.pyplot as plt
import struct
 
 
class MDFViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Plot Browser")
 
        self.mdf = None
        self.dbc = None
        self.signal_names = []
        self.decoded_signals = {}
 
        # Load buttons
        self.load_mf4_button = tk.Button(root, text="Load MF4 File", command=self.load_mf4)
        self.load_mf4_button.pack(pady=5)
 
        self.load_dbc_button = tk.Button(root, text="Load DBC File", command=self.load_dbc)
        self.load_dbc_button.pack(pady=5)
 
        # Listbox for signal selection
        self.listbox = Listbox(root, selectmode=MULTIPLE, width=50, height=20)
        self.listbox.pack(pady=10)
 
        # Plot button
        self.plot_button = tk.Button(root, text="Plot Selected Signals", command=self.plot_signals)
 
        # Plot mode selector
        self.plot_mode_var = tk.StringVar(value="same")  # default to "same graph"
 
        self.plot_same_radio = tk.Radiobutton(root, text="Plot on Same Graph", variable=self.plot_mode_var, value="same")
        self.plot_same_radio.pack()
 
        self.plot_subplots_radio = tk.Radiobutton(root, text="Plot on Subplots", variable=self.plot_mode_var, value="subplots")
        self.plot_subplots_radio.pack()
 
        self.show_dots_var = tk.BooleanVar(value=False)
 
        self.show_dots_checkbox = tk.Checkbutton(
            root, text="Show Dots on Graph", variable=self.show_dots_var
        )
        self.show_dots_checkbox.pack()
 
        self.plot_button.pack(pady=10)
 
    def load_mf4(self):
        file_path = filedialog.askopenfilename(filetypes=[("MF4 files", "*.mf4")])
        if not file_path:
            return
 
        try:
            self.mdf = MDF(file_path)
            messagebox.showinfo("Success", f"Loaded MF4 file.")
            if self.dbc:
                self.decode_signals()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load MF4 file:\n{e}")
       
 
        can_data = self.mdf.get("CAN_DataFrame")
 
    def load_dbc(self):
        file_path = filedialog.askopenfilename(filetypes=[("DBC files", "*.dbc")])
        if not file_path:
            return
 
        try:
            # load with cantools for manual decoding if needed
            self.dbc = cantools.database.load_file(file_path)
 
            messagebox.showinfo("Success", "DBC file loaded.")
 
            if self.mdf:
                self.decode_signals()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load DBC file:\n{e}")
 
    def get_signal_unit(self, signal_name):
        for message in self.dbc.messages:
            for signal in message.signals:
                if signal.name == signal_name:
                    return signal.unit or ""
        return ""
 
 
    def decode_signals(self):
        self.signal_names.clear()
        self.decoded_signals.clear()
        self.listbox.delete(0, tk.END)
 
        try:
            # Load signals
            can_id_signal = self.mdf.get('CAN_DataFrame.ID')
            data_bytes_signal = self.mdf.get('CAN_DataFrame.DataBytes')
 
            n = len(can_id_signal.samples)
 
            for i in range(n):
                try:
                    can_id = int(can_id_signal.samples[i]) & 0x1FFFFFFF
                    timestamp = can_id_signal.timestamps[i]
 
                    raw_bytes = data_bytes_signal.samples[i]
                    # Convert to bytes — ensure all elements are ints
                    data = bytes([int(b) for b in raw_bytes])
 
                    decoded = self.dbc.decode_message(can_id, data)
 
                    for signal_name, value in decoded.items():
                        if signal_name not in self.decoded_signals:
                            self.decoded_signals[signal_name] = {'timestamps': [], 'values': []}
                        self.decoded_signals[signal_name]['timestamps'].append(timestamp)
                        self.decoded_signals[signal_name]['values'].append(value)
 
                except Exception as e:
                    continue
 
            self.signal_names = list(self.decoded_signals.keys())
            for name in self.signal_names:
                self.listbox.insert(tk.END, name)
 
            messagebox.showinfo("Decoded", f"Found {len(self.signal_names)} decoded signals.")
 
        except Exception as e:
            messagebox.showerror("Error", f"Failed to decode signals:\n{e}")
 
 
    def plot_signals(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select at least one signal.")
            return
 
        selected_signals = [self.listbox.get(idx) for idx in selected_indices]
        plot_mode = self.plot_mode_var.get()
        show_dots = self.show_dots_var.get()
        line_kwargs = {'linestyle': '-', 'marker': 'o' if show_dots else ''}
 
        if plot_mode == "same":
            plt.figure()
            for signal_name in selected_signals:
                data = self.decoded_signals.get(signal_name)
                if data:
                    plt.plot(data['timestamps'], data['values'], label=signal_name, **line_kwargs)
            plt.legend()
            plt.title("Decoded CAN Signals")
            plt.xlabel("Time [s]")
            plt.ylabel("Value (variable units)")
            plt.grid(True)
 
        elif plot_mode == "subplots":
            fig, axs = plt.subplots(len(selected_signals), 1, sharex=True, figsize=(10, 3 * len(selected_signals)))
            if len(selected_signals) == 1:
                axs = [axs]
            for ax, signal_name in zip(axs, selected_signals):
                data = self.decoded_signals.get(signal_name)
                if data:
                    ax.plot(data['timestamps'], data['values'], **line_kwargs)
                    unit = self.get_signal_unit(signal_name)
                    ax.set_title(f"{signal_name} ({unit})" if unit else signal_name)
                    ax.set_ylabel(unit if unit else "Value")
                    ax.grid(True)
            axs[-1].set_xlabel("Time [s]")
 
        plt.tight_layout()
        plt.show()
 
# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = MDFViewerApp(root)
    root.mainloop()
 
 