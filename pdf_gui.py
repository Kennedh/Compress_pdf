"""Interface desktop em português para o compressor com PyMuPDF."""

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_version import VERSION

from compress_pdf import (
    PRESETS, CompressionCancelled, CompressionError,
    compress_pdf, check_pymupdf, format_size, validate_pdf,
)


class PDFCompressorApp:
    def __init__(self, root):
        self.root = root
        self.files = {}
        self.details = {}
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.closing = False
        self.saved_bytes = 0
        self.finished_count = 0
        self.failed_count = 0
        self.last_output_dir = None
        self.destination = tk.StringVar()
        self.preset = tk.StringVar(value=PRESETS["ebook"][0])
        self.status = tk.StringVar(value="Adicione seus PDFs para começar.")
        self.count_text = tk.StringVar(value="0 arquivos")
        self.size_text = tk.StringVar(value="0,0 B")
        self.savings_text = tk.StringVar(value="0,0 B")
        self.profile_text = tk.StringVar(value=PRESETS["ebook"][1])
        self.root.title(f"Compress PDF {VERSION}")
        self.root.geometry("1080x780")
        self.root.minsize(860, 700)
        self.root.configure(bg="#f3f6fa")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._build()
        self.poll_id = self.root.after(100, self._poll)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        font = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
        self.font = font
        style.configure(".", font=(font, 10), background="#f3f6fa", foreground="#192b43")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff")
        style.configure("Muted.TLabel", foreground="#52647a")
        style.configure("Title.TLabel", font=(font, 12, "bold"))
        style.configure("Stat.TLabel", font=(font, 20, "bold"), background="#ffffff")
        style.configure("TButton", padding=(14, 9), borderwidth=0, background="#e4ebf3")
        style.map("TButton", background=[("active", "#d6e2ee")],
                  foreground=[("disabled", "#7c899a")])
        style.configure("Accent.TButton", background="#087f76", foreground="#ffffff",
                        font=(font, 10, "bold"))
        style.map("Accent.TButton", background=[("disabled", "#a8c7c3"), ("active", "#08685f")],
                  foreground=[("disabled", "#ffffff")])
        style.configure("TEntry", padding=7, fieldbackground="#ffffff")
        style.configure("TCombobox", padding=7, fieldbackground="#ffffff")
        style.configure("Treeview", rowheight=36, background="#ffffff",
                        fieldbackground="#ffffff", borderwidth=0)
        style.configure("Treeview.Heading", background="#e9eff6",
                        font=(font, 9, "bold"), padding=(10, 10))
        style.map("Treeview", background=[("selected", "#dcefeb")],
                  foreground=[("selected", "#153c36")])
        style.configure("Horizontal.TProgressbar", background="#087f76", troughcolor="#e0e7ef",
                        borderwidth=0, thickness=7)

    def _build(self):
        header = tk.Frame(self.root, bg="#172c46", padx=28, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="COMPRESS PDF", bg="#172c46", fg="#79d8c8",
                 font=(self.font, 10, "bold")).pack(anchor="w")
        tk.Label(header, text="Menos tamanho. Mais espaço.", bg="#172c46", fg="white",
                 font=(self.font, 24, "bold")).pack(anchor="w", pady=(6, 4))
        tk.Label(header, text="Comprima seus PDFs em lote, com os originais sempre preservados.",
                 bg="#172c46", fg="#c4d2e2", font=(self.font, 10)).pack(anchor="w")

        body = ttk.Frame(self.root, padding=(24, 18))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        stats = ttk.Frame(body)
        stats.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        for index, (label, variable) in enumerate((
            ("NA FILA", self.count_text), ("TAMANHO ORIGINAL", self.size_text),
            ("ESPAÇO ECONOMIZADO · ÚLTIMO LOTE", self.savings_text),
        )):
            card = ttk.Frame(stats, style="Card.TFrame", padding=(16, 12))
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            stats.columnconfigure(index, weight=1, uniform="cards")
            ttk.Label(card, text=label, style="Card.TLabel",
                      font=(self.font, 8, "bold"), foreground="#52647a").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style="Stat.TLabel").pack(anchor="w", pady=(5, 0))

        toolbar = ttk.Frame(body)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(toolbar, text="Seus arquivos", style="Title.TLabel").pack(side="left")
        self.add_button = ttk.Button(toolbar, text="+ Adicionar PDFs", command=self.add_files)
        self.add_button.pack(side="right")
        self.remove_button = ttk.Button(toolbar, text="Remover selecionados", command=self.remove_selected)
        self.remove_button.pack(side="right", padx=(0, 8))

        table = ttk.Frame(body)
        table.grid(row=2, column=0, sticky="nsew")
        self.tree = ttk.Treeview(table, columns=("name", "original", "output", "reduction", "status"),
                                 show="headings", selectmode="extended", height=5)
        columns = (
            ("name", "ARQUIVO", 300, "w"),
            ("original", "ORIGINAL", 110, "e"),
            ("output", "FINAL", 110, "e"),
            ("reduction", "REDUÇÃO", 100, "e"),
            ("status", "STATUS", 175, "w"),
        )
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, minwidth=75, anchor=anchor, stretch=key == "name")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.tag_configure("success", foreground="#08735e")
        self.tree.tag_configure("error", foreground="#b33838")
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)

        self.detail_text = tk.Text(body, height=2, wrap="word", relief="flat", bg="#f3f6fa",
                                   fg="#52647a", font=(self.font, 9), state="disabled")
        self.detail_text.grid(row=3, column=0, sticky="ew", pady=(7, 10))
        self._set_detail("Os PDFs aparecerão aqui. Selecione uma linha para ver os caminhos e detalhes.")

        options = ttk.Frame(body, style="Card.TFrame", padding=16)
        options.grid(row=4, column=0, sticky="ew")
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=2)
        ttk.Label(options, text="Qualidade da compressão", style="Card.TLabel",
                  font=(self.font, 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="Pasta de destino (opcional)", style="Card.TLabel",
                  font=(self.font, 10, "bold")).grid(row=0, column=1, sticky="w", padx=(22, 0))
        self.preset_box = ttk.Combobox(options, textvariable=self.preset, state="readonly",
                                       values=[value[0] for value in PRESETS.values()], width=25)
        self.preset_box.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        self.preset_box.bind("<<ComboboxSelected>>", self._profile_changed)
        destination_row = ttk.Frame(options, style="Card.TFrame")
        destination_row.grid(row=1, column=1, sticky="ew", padx=(22, 0), pady=(8, 4))
        self.destination_entry = ttk.Entry(destination_row, textvariable=self.destination)
        self.destination_entry.pack(side="left", fill="x", expand=True)
        self.folder_button = ttk.Button(destination_row, text="Escolher…", command=self.choose_folder)
        self.folder_button.pack(side="left", padx=(8, 0))
        ttk.Label(options, textvariable=self.profile_text, style="Card.TLabel",
                  foreground="#52647a", font=(self.font, 9)).grid(row=2, column=0, sticky="w")
        ttk.Label(options, text="Vazio: salva ao lado de cada original, com sufixo _comprimido.",
                  style="Card.TLabel", foreground="#52647a", font=(self.font, 9)
                  ).grid(row=2, column=1, sticky="w", padx=(22, 0))

        footer = ttk.Frame(body)
        footer.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        self.start_button = ttk.Button(footer, text="Comprimir PDFs", style="Accent.TButton",
                                       command=self.start, state="disabled")
        self.start_button.pack(side="right")
        self.cancel_button = ttk.Button(footer, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 8))
        self.open_button = ttk.Button(footer, text="Abrir pasta", command=self.open_folder, state="disabled")
        self.open_button.pack(side="left")
        self.progress = ttk.Progressbar(body, mode="determinate")
        self.progress.grid(row=6, column=0, sticky="ew", pady=(14, 8))
        ttk.Label(body, textvariable=self.status, style="Muted.TLabel").grid(row=7, column=0, sticky="w")
        try:
            self.engine_version = check_pymupdf()
            dependency = f"PyMuPDF {self.engine_version} · processamento local"
        except CompressionError:
            self.engine_version = None
            dependency = "PyMuPDF não encontrado · instale para comprimir"
        ttk.Label(body, text=dependency, style="Muted.TLabel",
                  font=(self.font, 8)).grid(row=8, column=0, sticky="w", pady=(6, 0))

    @property
    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def add_files(self):
        if self.running:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title="Adicionar PDFs",
                                            filetypes=[("Documentos PDF", "*.pdf *.PDF")])
        errors = []
        for filename in paths:
            try:
                path = validate_pdf(filename)
                if path in self.files.values():
                    continue
                size = path.stat().st_size
                item = self.tree.insert("", "end", values=(path.name, format_size(size), "—", "—", "Na fila"))
                self.files[item] = path
                self.details[item] = f"Original: {path}"
            except (CompressionError, OSError) as exc:
                errors.append(str(exc))
        self._refresh_selection()
        if errors:
            messagebox.showwarning("Arquivos não adicionados", "\n\n".join(errors), parent=self.root)

    def remove_selected(self):
        if self.running:
            return
        for item in self.tree.selection():
            self.tree.delete(item)
            self.files.pop(item, None)
            self.details.pop(item, None)
        self._refresh_selection()

    def _refresh_selection(self):
        count = len(self.files)
        total = 0
        for path in self.files.values():
            try:
                total += path.stat().st_size
            except OSError:
                pass  # O erro será apresentado na linha ao processar.
        self.count_text.set(f"{count} arquivo" if count == 1 else f"{count} arquivos")
        self.size_text.set(format_size(total))
        self.start_button.configure(state="normal" if count else "disabled")
        self.status.set("Pronto para comprimir." if count else "Adicione seus PDFs para começar.")

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Pasta dos PDFs comprimidos")
        if folder:
            self.destination.set(folder)

    def _profile_changed(self, _event=None):
        for title, description in PRESETS.values():
            if title == self.preset.get():
                self.profile_text.set(description)
                break

    def _set_detail(self, text):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _show_detail(self, _event=None):
        selected = self.tree.selection()
        if selected:
            self._set_detail(self.details.get(selected[0], ""))

    def _set_busy(self, busy):
        for widget in (self.add_button, self.remove_button, self.folder_button, self.destination_entry):
            widget.configure(state="disabled" if busy else "normal")
        self.preset_box.configure(state="disabled" if busy else "readonly")
        self.start_button.configure(state="disabled" if busy or not self.files else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def start(self):
        if self.running or not self.files:
            return
        try:
            self.engine_version = check_pymupdf()
            destination = Path(self.destination.get().strip()).expanduser().resolve() if self.destination.get().strip() else None
            if destination is not None and not destination.is_dir():
                raise CompressionError("Escolha uma pasta de destino existente.")
        except (CompressionError, OSError) as exc:
            messagebox.showerror("Não foi possível iniciar", str(exc), parent=self.root)
            return
        preset = next(key for key, value in PRESETS.items() if value[0] == self.preset.get())
        jobs = []
        reserved = set(self.files.values())
        for item, source in self.files.items():
            folder = destination or source.parent
            output = folder / f"{source.stem}_comprimido.pdf"
            number = 2
            while output.exists() or output in reserved:
                output = folder / f"{source.stem}_comprimido_{number}.pdf"
                number += 1
            reserved.add(output)
            jobs.append((item, source, output))
            self.tree.set(item, "status", "Na fila")
            self.tree.set(item, "output", "—")
            self.tree.set(item, "reduction", "—")
            self.tree.item(item, tags=())
            self.details[item] = f"Original: {source}\nDestino: {output}"
        self.saved_bytes = self.finished_count = self.failed_count = 0
        self.savings_text.set(format_size(0))
        self.progress.configure(value=0, maximum=len(jobs))
        self.cancel_event.clear()
        self._set_busy(True)
        self.status.set("Iniciando compressão…")
        self.worker = threading.Thread(target=self._process, args=(jobs, preset), daemon=True)
        self.worker.start()

    def _process(self, jobs, preset):
        try:
            for item, source, output in jobs:
                if self.cancel_event.is_set():
                    break
                self.events.put(("started", item, source.name))
                try:
                    result = compress_pdf(source, output, preset, cancel_event=self.cancel_event)
                except CompressionCancelled:
                    break
                except (CompressionError, OSError) as exc:
                    self.events.put(("error", item, str(exc)))
                else:
                    self.events.put(("result", item, result))
        except Exception as exc:
            # Garante que a interface saia do estado ocupado mesmo em falhas inesperadas.
            self.events.put(("unexpected", None, str(exc)))
        finally:
            self.events.put(("done", None, self.cancel_event.is_set()))

    def _poll(self):
        self.poll_id = None
        try:
            while True:
                event, item, value = self.events.get_nowait()
                if event == "started":
                    self.tree.set(item, "status", "Comprimindo…")
                    self.status.set(f"Processando {self.finished_count + 1}/{len(self.files)}: {value}")
                elif event == "result":
                    self.finished_count += 1
                    self.saved_bytes += value.saved_bytes
                    self.tree.set(item, "original", format_size(value.original_size))
                    self.tree.set(item, "output", format_size(value.compressed_size))
                    self.tree.set(item, "reduction", f"{value.reduction_percent:.1f}%".replace(".", ","))
                    self.tree.set(item, "status", "Concluído" if value.saved_bytes else "Sem redução")
                    self.tree.item(item, tags=("success",))
                    self.details[item] = f"Original: {value.input_path}\nSalvo em: {value.output_path}"
                    if not value.saved_bytes:
                        self.details[item] += " · Mantida uma cópia do original."
                    self.last_output_dir = value.output_path.parent
                    self.open_button.configure(state="normal")
                    self.savings_text.set(format_size(self.saved_bytes))
                    self.progress.configure(value=self.finished_count)
                elif event == "error":
                    self.finished_count += 1
                    self.failed_count += 1
                    self.tree.set(item, "status", "Erro · veja detalhes")
                    self.tree.item(item, tags=("error",))
                    self.details[item] = value
                    self._set_detail(value)
                    self.progress.configure(value=self.finished_count)
                elif event == "unexpected":
                    self._set_detail(f"Falha inesperada: {value}")
                    self.failed_count += 1
                elif event == "done":
                    for row in self.files:
                        if self.tree.set(row, "status") in ("Na fila", "Comprimindo…"):
                            self.tree.set(row, "status", "Cancelado" if value else "Não processado")
                    self._set_busy(False)
                    successes = self.finished_count - self.failed_count
                    self.status.set(
                        f"{'Cancelado' if value else 'Finalizado'} · {max(0, successes)} concluído(s)"
                        f" · {self.failed_count} erro(s) · {format_size(self.saved_bytes)} economizados."
                    )
                    if self.closing:
                        self._destroy()
                        return
                if item in self.tree.selection():
                    self._show_detail()
        except queue.Empty:
            pass
        self.poll_id = self.root.after(100, self._poll)

    def cancel(self):
        if self.running:
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.status.set("Cancelando… os arquivos já concluídos serão mantidos.")

    def open_folder(self):
        if self.last_output_dir is None:
            return
        try:
            if os.name == "nt":
                os.startfile(self.last_output_dir)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self.last_output_dir)])
        except OSError as exc:
            messagebox.showerror("Não foi possível abrir a pasta", str(exc), parent=self.root)

    def _destroy(self):
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        self.root.destroy()

    def close(self):
        if self.running:
            self.closing = True
            self.cancel()
            self.status.set("Encerrando o processamento…")
        else:
            self._destroy()


def launch():
    root = tk.Tk()
    PDFCompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
