import matplotlib

matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, MULTIPLE
from asammdf import MDF
import cantools
import matplotlib.pyplot as plt
from cantools.database.can.signal import NamedSignalValue
from collections import defaultdict


class MDFViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Plot Browser")

        self.mdf = None
        self.dbc = None
        self.signal_names = []
        self.decoded_signals = {}
        self.enum_maps = defaultdict(dict)

        # Load buttons
        self.load_mf4_button = tk.Button(
            root, text="Load MF4 File", command=self.load_mf4
        )
        self.load_mf4_button.pack(pady=5)

        self.load_dbc_button = tk.Button(
            root, text="Load DBC File", command=self.load_dbc
        )
        self.load_dbc_button.pack(pady=5)

        # Signal filter
        self.filter_var = tk.StringVar()
        self.filter_entry = tk.Entry(root, textvariable=self.filter_var, width=50)
        self.filter_entry.insert(0, "Filter signals...")
        self.filter_entry.config(fg="grey")
        self.filter_entry.bind("<FocusIn>", self._filter_focus_in)
        self.filter_entry.bind("<FocusOut>", self._filter_focus_out)
        self.filter_entry.pack()

        # Listbox for signal selection
        self.listbox = Listbox(root, selectmode=MULTIPLE, width=50, height=20)
        self.listbox.pack(pady=10)

        self.filter_var.trace_add("write", lambda *_: self.filter_signals())

        # Plot button
        self.plot_button = tk.Button(
            root, text="Plot Selected Signals", command=self.plot_signals
        )

        # Plot mode selector
        self.plot_mode_var = tk.StringVar(value="same")

        self.plot_same_radio = tk.Radiobutton(
            root, text="Plot on Same Graph", variable=self.plot_mode_var, value="same"
        )
        self.plot_same_radio.pack()

        self.plot_subplots_radio = tk.Radiobutton(
            root, text="Plot on Subplots", variable=self.plot_mode_var, value="subplots"
        )
        self.plot_subplots_radio.pack()

        self.show_dots_var = tk.BooleanVar(value=False)
        self.show_dots_checkbox = tk.Checkbutton(
            root, text="Show Dots on Graph", variable=self.show_dots_var
        )
        self.show_dots_checkbox.pack()

        self.use_raw_can_var = tk.BooleanVar(value=True)
        self.use_raw_can_checkbox = tk.Checkbutton(
            root, text="Decode Raw CAN using DBC", variable=self.use_raw_can_var
        )
        self.use_raw_can_checkbox.pack()

        # Time range
        time_frame = tk.Frame(root)
        time_frame.pack(pady=5)
        tk.Label(time_frame, text="Start time (s):").grid(row=0, column=0, padx=4)
        self.start_time_var = tk.StringVar()
        tk.Entry(time_frame, textvariable=self.start_time_var, width=10).grid(
            row=0, column=1, padx=4
        )
        tk.Label(time_frame, text="End time (s):").grid(row=0, column=2, padx=4)
        self.end_time_var = tk.StringVar()
        tk.Entry(time_frame, textvariable=self.end_time_var, width=10).grid(
            row=0, column=3, padx=4
        )

        self.plot_button.pack(pady=10)

    def _filter_focus_in(self, _):
        if self.filter_entry.cget("fg") == "grey":
            self.filter_entry.delete(0, tk.END)
            self.filter_entry.config(fg="black")

    def _filter_focus_out(self, _):
        if not self.filter_var.get():
            self.filter_entry.insert(0, "Filter signals...")
            self.filter_entry.config(fg="grey")

    def filter_signals(self):
        query = self.filter_var.get().lower()
        self.listbox.delete(0, tk.END)
        for name in self.signal_names:
            if query in name.lower():
                self.listbox.insert(tk.END, name)

    def _parse_time_range(self):
        """Return (t_start, t_end) floats or None if field is empty. Raises ValueError on bad input."""
        t_start = (
            float(self.start_time_var.get())
            if self.start_time_var.get().strip()
            else None
        )
        t_end = (
            float(self.end_time_var.get()) if self.end_time_var.get().strip() else None
        )
        return t_start, t_end

    def _apply_time_range(self, timestamps, values, t_start, t_end):
        import numpy as np

        ts = np.asarray(timestamps)
        vs = np.asarray(values)
        mask = np.ones(len(ts), dtype=bool)
        if t_start is not None:
            mask &= ts >= t_start
        if t_end is not None:
            mask &= ts <= t_end
        return ts[mask], vs[mask]

    def load_mf4(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("MDF/MF4 files", "*.mf4 *.mdf"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            self.mdf = MDF(file_path)
            messagebox.showinfo("Success", "Loaded MDF file.")

            has_raw_can = "CAN_DataFrame.ID" in self.mdf.channels_db

            if has_raw_can and self.use_raw_can_var.get():
                if self.dbc:
                    self.decode_signals()
                else:
                    messagebox.showwarning(
                        "Warning",
                        "Raw CAN frames detected but no DBC loaded.\n"
                        "Load a DBC to decode, or uncheck 'Decode Raw CAN' to read pre-decoded channels.",
                    )
            else:
                self.load_decoded_channels_from_mf4()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load MDF file:\n{e}")

    def load_decoded_channels_from_mf4(self):
        self.signal_names.clear()
        self.decoded_signals.clear()
        self.listbox.delete(0, tk.END)

        # Skip raw CAN transport fields and bare timestamp channels
        skip_keywords = [
            "CAN_DataFrame",
            "DataBytes",
            "Dir",
            "BRS",
            "ESI",
            "IDE",
            "DLC",
        ]

        try:
            seen = set()

            for group_index, group in enumerate(self.mdf.groups):
                for channel_index, channel in enumerate(group.channels):
                    channel_name = channel.name

                    # Skip exact timestamp channel and raw CAN fields
                    if channel_name == "t":
                        continue
                    if any(k in channel_name for k in skip_keywords):
                        continue

                    unique_key = (
                        channel_name
                        if channel_name not in seen
                        else f"{channel_name} [g{group_index}]"
                    )
                    seen.add(channel_name)

                    try:
                        signal = self.mdf.get(
                            channel_name, group=group_index, index=channel_index
                        )
                        self.decoded_signals[unique_key] = {
                            "timestamps": signal.timestamps,
                            "values": signal.samples,
                            "unit": signal.unit or "",
                        }
                        self.signal_names.append(unique_key)
                    except Exception:
                        continue

            for name in self.signal_names:
                self.listbox.insert(tk.END, name)

            messagebox.showinfo(
                "Info", f"Found {len(self.signal_names)} decoded signals in MDF."
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load decoded signals:\n{e}")

    def load_dbc(self):
        file_path = filedialog.askopenfilename(filetypes=[("DBC files", "*.dbc")])
        if not file_path:
            return

        try:
            self.dbc = cantools.database.load_file(file_path)
            messagebox.showinfo("Success", "DBC file loaded.")

            if self.mdf:
                self.decode_signals()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load DBC file:\n{e}")

    def get_signal_unit(self, signal_name):
        if self.dbc:
            for message in self.dbc.messages:
                for signal in message.signals:
                    if signal.name == signal_name:
                        return signal.unit or ""

        data = self.decoded_signals.get(signal_name, {})
        return data.get("unit", "")

    def decode_signals(self):
        self.signal_names.clear()
        self.decoded_signals.clear()
        self.enum_maps = defaultdict(dict)
        self.listbox.delete(0, tk.END)

        try:
            can_id_signal = self.mdf.get("CAN_DataFrame.ID")
            data_bytes_signal = self.mdf.get("CAN_DataFrame.DataBytes")
            n = len(can_id_signal.samples)

            for i in range(n):
                try:
                    can_id = int(can_id_signal.samples[i]) & 0x1FFFFFFF
                    timestamp = can_id_signal.timestamps[i]
                    raw_bytes = data_bytes_signal.samples[i]
                    data = bytes([int(b) for b in raw_bytes])
                    decoded = self.dbc.decode_message(can_id, data)

                    for signal_name, value in decoded.items():
                        if isinstance(value, NamedSignalValue):
                            int_val = int(value.value)
                            str_val = str(value)
                            self.enum_maps[signal_name][int_val] = str_val
                            value = int_val

                        if signal_name not in self.decoded_signals:
                            self.decoded_signals[signal_name] = {
                                "timestamps": [],
                                "values": [],
                                "unit": "",
                            }

                        self.decoded_signals[signal_name]["timestamps"].append(
                            timestamp
                        )
                        self.decoded_signals[signal_name]["values"].append(value)

                except Exception:
                    continue

            self.signal_names = list(self.decoded_signals.keys())
            for name in self.signal_names:
                self.listbox.insert(tk.END, name)

            if not self.signal_names:
                messagebox.showwarning(
                    "No Signals", "No valid signals were decoded from the CAN frames."
                )
            else:
                messagebox.showinfo(
                    "Decoded", f"Found {len(self.signal_names)} decoded signals."
                )

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
        marker = "o" if show_dots else ""
        line_kwargs = {"linestyle": "-", "marker": marker}

        try:
            t_start, t_end = self._parse_time_range()
        except ValueError:
            messagebox.showerror(
                "Invalid Time", "Start/End time must be numbers (e.g. 10.5)."
            )
            return

        if plot_mode == "same":
            plt.figure(figsize=(12, 6))
            plotted = False
            for signal_name in selected_signals:
                data = self.decoded_signals.get(signal_name)
                if data is not None and len(data["timestamps"]) > 0:
                    ts, vs = self._apply_time_range(
                        data["timestamps"], data["values"], t_start, t_end
                    )
                    if len(ts) == 0:
                        continue
                    plt.plot(ts, vs, label=signal_name, **line_kwargs)
                    plotted = True
            if not plotted:
                messagebox.showwarning(
                    "No Data", "No data found for the selected signals."
                )
                plt.close()
                return
            plt.title("Signals")
            plt.xlabel("Time [s]")
            plt.ylabel("Value")
            plt.legend()
            plt.grid(True)

        elif plot_mode == "subplots":
            fig, axs = plt.subplots(
                len(selected_signals),
                1,
                sharex=True,
                figsize=(12, 3 * len(selected_signals)),
            )
            if len(selected_signals) == 1:
                axs = [axs]

            for ax, signal_name in zip(axs, selected_signals):
                data = self.decoded_signals.get(signal_name)
                if data is not None and len(data["timestamps"]) > 0:
                    ts, vs = self._apply_time_range(
                        data["timestamps"], data["values"], t_start, t_end
                    )
                    ax.plot(ts, vs, **line_kwargs)
                    unit = self.get_signal_unit(signal_name)
                    title = f"{signal_name} ({unit})" if unit else signal_name
                    ax.set_title(title)
                    ax.set_ylabel(unit if unit else "Value")
                    ax.grid(True)

                    enum_map = self.enum_maps.get(signal_name)
                    if enum_map:
                        legend_entries = [
                            f"{k} = {v}" for k, v in sorted(enum_map.items())
                        ]
                        legend_text = "\n".join(legend_entries)
                        ax.text(
                            1.01,
                            0.5,
                            legend_text,
                            transform=ax.transAxes,
                            fontsize=9,
                            va="center",
                            ha="left",
                            bbox=dict(boxstyle="round", fc="w"),
                        )
                else:
                    ax.set_title(f"{signal_name} (no data)")
                    ax.grid(True)

            axs[-1].set_xlabel("Time [s]")

        plt.tight_layout()
        plt.show()


# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = MDFViewerApp(root)
    root.mainloop()
