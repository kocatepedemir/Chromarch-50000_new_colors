import sqlite3

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    # tkinter is unavailable in browser (Pyodide) environments. The pure
    # data/logic methods on ColorApp (e.g. parse_row_data) do not depend on
    # tkinter and can still be imported and called from there.
    tk = None

DB_NAME = "github_new_colors.db"
ITEMS_PER_PAGE = 24
PLACEHOLDER_TEXT = "Search colors, HEX, RGB..."

class ColorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub New Colors Explorer (50k Dataset)")
        self.root.geometry("950x680")
        self.root.configure(bg="#0d1117")

        self.tables = []
        self.selected_table = ""
        self.current_page = 1
        self.total_items = 0
        self.total_pages = 1
        self.db_path = DB_NAME

        self.setup_ui()

    def setup_ui(self):
        top_frame = tk.Frame(self.root, bg="#161b22", pady=12, padx=15)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        title = tk.Label(
            top_frame, 
            text="GitHub New Colors Explorer", 
            font=("Segoe UI", 15, "bold"), 
            fg="#58a6ff", 
            bg="#161b22"
        )
        title.pack(side=tk.LEFT, padx=5)

        load_btn = tk.Button(
            top_frame, 
            text="Load Database", 
            command=self.load_database,
            bg="#238636", 
            fg="white", 
            font=("Segoe UI", 10, "bold"),
            bd=0, 
            padx=12, 
            pady=5,
            cursor="hand2"
        )
        load_btn.pack(side=tk.RIGHT, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_entry = tk.Entry(
            top_frame, 
            textvariable=self.search_var, 
            font=("Segoe UI", 10),
            bg="#010409", 
            fg="#c9d1d9", 
            insertbackground="white",
            bd=1, 
            relief=tk.SOLID
        )
        self.search_entry.pack(side=tk.RIGHT, padx=10, ipady=3)
        self.search_entry.insert(0, PLACEHOLDER_TEXT)
        self.search_entry.bind("<FocusIn>", self.on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_search_focus_out)

        self.nav_frame = tk.Frame(self.root, bg="#161b22", pady=8, padx=15)
        self.nav_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.prev_btn = tk.Button(
            self.nav_frame, 
            text="◄ Previous", 
            command=self.prev_page,
            bg="#21262d", 
            fg="#c9d1d9", 
            state=tk.DISABLED,
            bd=0, 
            padx=10, 
            pady=4,
            cursor="hand2"
        )
        self.prev_btn.pack(side=tk.LEFT)

        self.page_label = tk.Label(
            self.nav_frame, 
            text="Page 0 of 0", 
            font=("Segoe UI", 10), 
            fg="#8b949e", 
            bg="#161b22"
        )
        self.page_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(
            self.nav_frame, 
            text="Next ►", 
            command=self.next_page,
            bg="#21262d", 
            fg="#c9d1d9", 
            state=tk.DISABLED,
            bd=0, 
            padx=10, 
            pady=4,
            cursor="hand2"
        )
        self.next_btn.pack(side=tk.RIGHT)

        main_container = tk.Frame(self.root, bg="#0d1117")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(main_container, bg="#0d1117", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        
        self.scroll_frame = tk.Frame(self.canvas, bg="#0d1117")
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.status_label = tk.Label(
            self.scroll_frame, 
            text="Click 'Load Database' to view 50k color dataset.", 
            font=("Segoe UI", 12), 
            fg="#8b949e", 
            bg="#0d1117"
        )
        self.status_label.pack(pady=50)

    def on_search_focus_in(self, event):
        if self.search_entry.get() == PLACEHOLDER_TEXT:
            self.search_entry.delete(0, tk.END)

    def on_search_focus_out(self, event):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, PLACEHOLDER_TEXT)

    def load_database(self):
        path = filedialog.askopenfilename(
            title="Select GitHub Colors Database",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if not path:
            return

        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            if not tables:
                messagebox.showinfo("Info", "Database is empty or has no tables.")
                conn.close()
                return

            self.tables = [t[0] for t in tables]
            self.selected_table = self.tables[0]
            self.db_path = path
            conn.close()

            self.current_page = 1
            self.fetch_and_render()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read database:\n{str(e)}")

    def fetch_and_render(self):
        if not self.selected_table:
            return

        query_text = self.search_var.get().strip()
        if query_text == PLACEHOLDER_TEXT:
            query_text = ""

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(f"PRAGMA table_info(`{self.selected_table}`)")
            columns = [col[1] for col in cursor.fetchall()]

            where_clause = ""
            params = []
            if query_text:
                conditions = [f"`{col}` LIKE ?" for col in columns]
                where_clause = " WHERE " + " OR ".join(conditions)
                params = [f"%{query_text}%"] * len(columns)

            count_sql = f"SELECT COUNT(*) FROM `{self.selected_table}`{where_clause}"
            cursor.execute(count_sql, params)
            self.total_items = cursor.fetchone()[0]

            self.total_pages = max(1, (self.total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

            offset = (self.current_page - 1) * ITEMS_PER_PAGE
            data_sql = f"SELECT * FROM `{self.selected_table}`{where_clause} LIMIT {ITEMS_PER_PAGE} OFFSET {offset}"
            cursor.execute(data_sql, params)
            rows = cursor.fetchall()

            conn.close()

            self.render_cards(columns, rows)
            self.update_pagination_controls()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to query database:\n{str(e)}")

    def render_cards(self, columns, rows):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.canvas.yview_moveto(0)

        if not rows:
            no_data = tk.Label(
                self.scroll_frame, 
                text="No matching colors found.", 
                font=("Segoe UI", 12), 
                fg="#8b949e", 
                bg="#0d1117"
            )
            no_data.pack(pady=50)
            return

        grid_frame = tk.Frame(self.scroll_frame, bg="#0d1117")
        grid_frame.pack(fill=tk.X, padx=10, pady=10)

        col_count = 3
        for i in range(col_count):
            grid_frame.columnconfigure(i, weight=1)

        for i, row in enumerate(rows):
            name, hex_val, rgb_val, extra = self.parse_row_data(columns, row)
            r, c = divmod(i, col_count)
            self.create_card(grid_frame, r, c, name, hex_val, rgb_val, extra)

    def parse_row_data(self, columns, row):
        name = "Color Item"
        hex_val = ""
        rgb_val = ""
        extra = []

        for idx, cell in enumerate(row):
            col_name = str(columns[idx]).lower()
            val = str(cell) if cell is not None else ""

            if "hex" in col_name or val.startswith("#"):
                hex_val = val if val.startswith("#") else f"#{val}"
            elif "rgb" in col_name or "rgb" in val:
                rgb_val = val
            elif "name" in col_name or "title" in col_name or "label" in col_name:
                name = val
            else:
                if not hex_val and (val.startswith("#") or len(val) == 6):
                    hex_val = val if val.startswith("#") else f"#{val}"
                else:
                    extra.append(f"{columns[idx]}: {val}")

        return name, hex_val, rgb_val, "\n".join(extra[:3])

    def create_card(self, parent, row, col, name, hex_code, rgb_code, extra_info):
        card = tk.Frame(parent, bg="#161b22", bd=1, relief=tk.SOLID)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        bg_color = hex_code if hex_code and len(hex_code) in (4, 7) else "#21262d"
        preview = tk.Frame(card, bg=bg_color, height=55)
        preview.pack(fill=tk.X)

        details = tk.Frame(card, bg="#161b22", padx=10, pady=8)
        details.pack(fill=tk.BOTH, expand=True)

        lbl_title = tk.Label(
            details, 
            text=name, 
            font=("Segoe UI", 10, "bold"), 
            fg="#f0f6fc", 
            bg="#161b22", 
            anchor="w",
            wraplength=220,
            justify=tk.LEFT
        )
        lbl_title.pack(fill=tk.X)

        if hex_code:
            btn_hex = tk.Button(
                details, 
                text=f"HEX: {hex_code}", 
                font=("Consolas", 9, "bold"), 
                fg="#58a6ff", 
                bg="#010409", 
                bd=0,
                cursor="hand2",
                command=lambda: self.copy_to_clipboard(hex_code)
            )
            btn_hex.pack(fill=tk.X, pady=2)

        if rgb_code:
            btn_rgb = tk.Button(
                details, 
                text=f"RGB: {rgb_code}", 
                font=("Consolas", 8), 
                fg="#79c0ff", 
                bg="#010409", 
                bd=0,
                cursor="hand2",
                command=lambda: self.copy_to_clipboard(rgb_code)
            )
            btn_rgb.pack(fill=tk.X, pady=2)

        if extra_info:
            lbl_extra = tk.Label(
                details, 
                text=extra_info, 
                font=("Segoe UI", 8), 
                fg="#8b949e", 
                bg="#161b22", 
                anchor="w",
                justify=tk.LEFT,
                wraplength=220
            )
            lbl_extra.pack(fill=tk.X, pady=(2, 0))

    def update_pagination_controls(self):
        if self.total_items == 0:
            self.page_label.config(text="No results found")
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            return

        self.page_label.config(text=f"Page {self.current_page} of {self.total_pages:,} ({self.total_items:,} colors)")
        self.prev_btn.config(state=tk.NORMAL if self.current_page > 1 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.current_page < self.total_pages else tk.DISABLED)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.fetch_and_render()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.fetch_and_render()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Copied", f"Copied to clipboard: {text}")

    def on_search_change(self, *args):
        if self.selected_table:
            self.current_page = 1
            self.fetch_and_render()

if __name__ == "__main__":
    root = tk.Tk()
    app = ColorApp(root)
    root.mainloop()
