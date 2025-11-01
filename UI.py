import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, filedialog
import json
import csv
import time
from datetime import datetime
from backend import DBAssistantBackend

class DBAssistantUI:
    def __init__(self, root, backend):
        self.root = root
        self.backend = backend
        self.root.title("MySQL AI Assistant - Enhanced")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        # Configuration
        self.config = {
            'font': ('Segoe UI', 12),
            'font_small': ('Segoe UI', 10),
            'themes': {
                'light': {'bg': '#F7F9FC', 'fg': '#333333', 'entry_bg': '#FFFFFF', 'entry_fg': '#333333', 'button_bg': '#E0E7FF', 'button_fg': '#333333', 'frame_bg': '#E8ECEF', 'highlight': '#6366F1'}
            },
            'suggestions': ['SELECT * FROM', 'CREATE TABLE', 'INSERT INTO', 'UPDATE', 'DELETE FROM', 'SHOW TABLES', 'DESCRIBE', 'ALTER TABLE']
        }
        self.mode = 'light'
        self.query_history = []
        self.last_execution_time = None

        # Initialize styles
        self.style = ttk.Style()
        self.style.configure('Toolbar.TFrame', background=self.config['themes'][self.mode]['frame_bg'])
        self.style.configure('Chat.TFrame', background=self.config['themes'][self.mode]['frame_bg'])
        self.style.configure('Schema.TFrame', background=self.config['themes'][self.mode]['frame_bg'])
        self.style.configure('Results.TFrame', background=self.config['themes'][self.mode]['frame_bg'])
        self.style.configure('History.TFrame', background=self.config['themes'][self.mode]['frame_bg'])
        self.style.configure('TButton', font=self.config['font_small'])
        self.style.configure('TEntry', fieldbackground=self.config['themes'][self.mode]['entry_bg'], foreground=self.config['themes'][self.mode]['entry_fg'])
        self.style.configure('Treeview', background=self.config['themes'][self.mode]['bg'], foreground=self.config['themes'][self.mode]['fg'], fieldbackground=self.config['themes'][self.mode]['bg'])

        # Main container with paned window
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left pane: Chat and Schema
        self.left_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.left_pane, weight=1)

        # Chat frame
        self.chat_frame = ttk.Frame(self.left_pane, style='Chat.TFrame')
        self.left_pane.add(self.chat_frame, weight=3)

        self.chat_label = ttk.Label(self.chat_frame, text="Chat with AI", font=self.config['font'])
        self.chat_label.pack(anchor='w', padx=5, pady=5)

        self.chat_history = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, width=50, height=20, font=self.config['font_small'])
        self.chat_history.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.chat_history.config(state=tk.DISABLED)

        # Input frame with autocomplete
        self.input_frame = ttk.Frame(self.chat_frame, style='Chat.TFrame')
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.input_entry = ttk.Entry(self.input_frame, font=self.config['font'])
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", self.send_message)
        self.input_entry.bind("<Control-Return>", self.send_message)
        self.input_entry.bind("<Tab>", self.autocomplete)

        # Schema frame
        self.schema_frame = ttk.Frame(self.left_pane, style='Schema.TFrame')
        self.left_pane.add(self.schema_frame, weight=1)

        self.schema_label = ttk.Label(self.schema_frame, text="Database Schema", font=self.config['font'])
        self.schema_label.pack(anchor='w', padx=5, pady=5)

        self.schema_tree = ttk.Treeview(self.schema_frame, show='tree', height=10)
        self.schema_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.schema_tree.bind("<Double-1>", self.insert_table_name)

        # Right pane: Results and History
        self.right_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.right_pane, weight=1)

        # Results frame
        self.results_frame = ttk.Frame(self.right_pane, style='Results.TFrame')
        self.right_pane.add(self.results_frame, weight=3)

        self.results_label = ttk.Label(self.results_frame, text="Query Results", font=self.config['font'])
        self.results_label.pack(anchor='w', padx=5, pady=5)

        self.results_display = scrolledtext.ScrolledText(self.results_frame, wrap=tk.WORD, width=50, height=20, font=self.config['font_small'])
        self.results_display.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.results_display.config(state=tk.DISABLED)

        # History frame
        self.history_frame = ttk.Frame(self.right_pane, style='History.TFrame')
        self.right_pane.add(self.history_frame, weight=1)

        self.history_label = ttk.Label(self.history_frame, text="Query History", font=self.config['font'])
        self.history_label.pack(anchor='w', padx=5, pady=5)

        self.history_listbox = tk.Listbox(self.history_frame, height=10, font=self.config['font_small'])
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_listbox.bind("<Double-1>", self.rerun_query)

        # Toolbar
        self.toolbar = ttk.Frame(self.root, style='Toolbar.TFrame')
        self.toolbar.pack(fill=tk.X, padx=5, pady=5)

        self.send_button = ttk.Button(self.toolbar, text="Send", command=self.send_message, style='TButton')
        self.send_button.pack(side=tk.LEFT, padx=5)
        self.send_button.bind("<Enter>", lambda e: self.show_tooltip(self.send_button, "Send query (Ctrl+Enter)"))

        self.clear_button = ttk.Button(self.toolbar, text="Clear Chat", command=self.clear_chat, style='TButton')
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.clear_button.bind("<Enter>", lambda e: self.show_tooltip(self.clear_button, "Clear chat history"))

        self.export_button = ttk.Button(self.toolbar, text="Export Results", command=self.export_results, style='TButton')
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.export_button.bind("<Enter>", lambda e: self.show_tooltip(self.export_button, "Export results as CSV"))

        self.reconnect_button = ttk.Button(self.toolbar, text="Reconnect", command=self.reconnect, style='TButton')
        self.reconnect_button.pack(side=tk.LEFT, padx=5)
        self.reconnect_button.bind("<Enter>", lambda e: self.show_tooltip(self.reconnect_button, "Reconnect to database"))

        # Status bar
        self.status_var = tk.StringVar(value="Initializing...")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, font=self.config['font_small'], relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(fill=tk.X, padx=5, pady=5)

        # Tooltip
        self.tooltip = None

        # Apply initial theme (fixed to light)
        self.apply_theme()

        # Initialize schema and connection
        self.load_schema()
        self.append_to_chat(self.backend.get_connection_status())
        self.update_status("Ready")

    def apply_theme(self):
        color_set = self.config['themes']['light']
        self.root.configure(bg=color_set['bg'])
        self.style.configure('Toolbar.TFrame', background=color_set['frame_bg'])
        self.style.configure('Chat.TFrame', background=color_set['frame_bg'])
        self.style.configure('Schema.TFrame', background=color_set['frame_bg'])
        self.style.configure('Results.TFrame', background=color_set['frame_bg'])
        self.style.configure('History.TFrame', background=color_set['frame_bg'])
        self.chat_label.configure(background=color_set['frame_bg'], foreground=color_set['fg'])
        self.schema_label.configure(background=color_set['frame_bg'], foreground=color_set['fg'])
        self.results_label.configure(background=color_set['frame_bg'], foreground=color_set['fg'])
        self.history_label.configure(background=color_set['frame_bg'], foreground=color_set['fg'])
        self.chat_history.configure(bg=color_set['bg'], fg=color_set['fg'])
        self.results_display.configure(bg=color_set['bg'], fg=color_set['fg'])
        self.input_entry.configure(style='TEntry')
        self.schema_tree.configure(style='Treeview')
        self.history_listbox.configure(bg=color_set['bg'], fg=color_set['fg'])
        self.style.configure('TEntry', fieldbackground=color_set['entry_bg'], foreground=color_set['entry_fg'])
        self.style.configure('TButton', background=color_set['button_bg'], foreground=color_set['button_fg'])
        self.style.map('TButton', background=[('active', color_set['highlight'])])
        self.style.configure('Treeview', background=color_set['bg'], foreground=color_set['fg'], fieldbackground=color_set['bg'])

    def append_to_chat(self, text):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, text + "\n", 'fade')
        self.chat_history.config(state=tk.DISABLED)
        self.chat_history.see(tk.END)
        # Fade-in effect
        self.chat_history.tag_configure('fade', foreground=self.config['themes']['light']['fg'])
        self.root.after(100, lambda: self.chat_history.tag_configure('fade', foreground=self.config['themes']['light']['fg']))

    def append_to_results(self, text):
        self.results_display.config(state=tk.NORMAL)
        self.results_display.delete(1.0, tk.END)
        self.results_display.insert(tk.END, text + "\n")
        self.results_display.config(state=tk.DISABLED)
        self.results_display.see(tk.END)

    def update_status(self, message):
        if self.last_execution_time:
            elapsed = f"Last query: {self.last_execution_time:.2f}s"
            self.status_var.set(f"{message} | {elapsed}")
        else:
            self.status_var.set(message)

    def show_tooltip(self, widget, text):
        if self.tooltip:
            self.tooltip.destroy()
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self.tooltip, text=text, background="#FFFFE0", relief='solid', borderwidth=1, font=self.config['font_small'])
        label.pack()
        widget.bind("<Leave>", lambda e: self.hide_tooltip())

    def hide_tooltip(self):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def load_schema(self):
        response, _ = self.backend.process_message("Show database schema")
        for item in self.schema_tree.get_children():
            self.schema_tree.delete(item)
        lines = response.split("\n")
        current_table = None
        for line in lines:
            if line.startswith("Table:"):
                table_name = line.split("Table: ")[1]
                current_table = self.schema_tree.insert("", "end", text=table_name, open=True)
            elif line.startswith("- ") and current_table:
                self.schema_tree.insert(current_table, "end", text=line[2:])

    def insert_table_name(self, event):
        selection = self.schema_tree.selection()
        if selection:
            item = self.schema_tree.item(selection[0])
            text = item['text']
            if not text.startswith("- "):  # Only insert table names, not columns
                self.input_entry.insert(tk.END, text + " ")

    def rerun_query(self, event):
        selection = self.history_listbox.curselection()
        if selection:
            query = self.history_listbox.get(selection[0])
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, query)
            self.send_message()

    def autocomplete(self, event):
        current = self.input_entry.get().strip()
        matches = [s for s in self.config['suggestions'] if s.lower().startswith(current.lower())]
        if matches:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, matches[0])
        return "break"

    def send_message(self, event=None):
        user_input = self.input_entry.get().strip()
        if not user_input:
            return
        self.append_to_chat(f"User: {user_input}")
        self.input_entry.delete(0, tk.END)
        self.query_history.append(user_input)
        self.history_listbox.insert(tk.END, user_input)
        self.history_listbox.see(tk.END)

        start_time = time.time()
        response, results = self.backend.process_message(user_input)
        self.last_execution_time = time.time() - start_time
        self.append_to_chat(f"AI: {response}\n")
        if results:
            self.append_to_results(results)
        self.update_status("Ready")

    def clear_chat(self):
        if messagebox.askyesno("Confirm", "Clear chat history?"):
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete(1.0, tk.END)
            self.chat_history.config(state=tk.DISABLED)
            self.results_display.config(state=tk.NORMAL)
            self.results_display.delete(1.0, tk.END)
            self.results_display.config(state=tk.DISABLED)
            self.history_listbox.delete(0, tk.END)
            self.query_history.clear()
            self.update_status("Chat cleared")

    def export_results(self):
        results = self.results_display.get(1.0, tk.END).strip()
        if not results:
            messagebox.showinfo("Export", "No results to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    for line in results.split("\n"):
                        writer.writerow(line.split(","))
                messagebox.showinfo("Export", "Results exported successfully.")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")

    def reconnect(self):
        self.append_to_chat(self.backend.get_connection_status())
        self.load_schema()
        self.update_status("Reconnected")

if __name__ == "__main__":
    from backend import DBAssistantBackend
    root = tk.Tk()
    backend = DBAssistantBackend()
    app = DBAssistantUI(root, backend)
    root.mainloop()