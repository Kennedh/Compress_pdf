"""Verificação executada pelo próprio aplicativo depois do empacotamento."""

import json
from pathlib import Path
import platform
import tempfile
import time
import traceback

from app_version import VERSION


def run(report_path):
    report = {"version": VERSION, "platform": platform.system(), "architecture": platform.machine()}
    root = None
    app = None
    try:
        import tkinter as tk
        import pymupdf
        from pdf_gui import PDFCompressorApp

        with tempfile.TemporaryDirectory(prefix="compress-smoke-") as directory:
            folder = Path(directory)
            source = folder / "relatório de teste.pdf"
            corrupt = folder / "corrompido.pdf"
            samples = bytes((index % 251 for index in range(512 * 512 * 3)))
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, 512, 512, samples, False)
            with pymupdf.open() as document:
                page = document.new_page()
                page.insert_text((30, 30), "Release smoke test")
                page.insert_image(pymupdf.Rect(30, 60, 330, 360), pixmap=pixmap)
                document.new_page().insert_text((30, 30), "Second page")
                document.save(source)
            corrupt.write_bytes(b"%PDF-1.4\ninvalid document")

            root = tk.Tk()
            root.withdraw()
            app = PDFCompressorApp(root)
            callback_errors = []
            root.report_callback_exception = lambda *args: callback_errors.append(str(args))
            for path in (source, corrupt):
                item = app.tree.insert("", "end", values=(path.name, "", "", "", "Na fila"))
                app.files[item] = path
                app.details[item] = str(path)
            app._refresh_selection()
            app.start()
            deadline = time.monotonic() + 90
            while str(app.start_button["state"]) != "normal":
                if time.monotonic() >= deadline:
                    raise RuntimeError("A interface não concluiu o teste em 90 segundos.")
                root.update()
                time.sleep(0.01)
            if callback_errors:
                raise RuntimeError("; ".join(callback_errors))
            if app.finished_count != 2 or app.failed_count != 1:
                raise RuntimeError(f"Resultado inesperado da fila: {app.status.get()}")
            if app.saved_bytes <= 0:
                raise RuntimeError("O PDF de exemplo não foi reduzido.")
            output = folder / "relatório de teste_comprimido.pdf"
            with pymupdf.open(output) as document:
                if document.page_count != 2 or "Release smoke test" not in document[0].get_text():
                    raise RuntimeError("O resultado perdeu páginas ou texto.")
                document[0].get_pixmap()
            error_item = list(app.files)[1]
            if not app.details[error_item]:
                raise RuntimeError("O erro de PDF inválido não foi informado.")
            if list(folder.glob(".compress-*")):
                raise RuntimeError("O processamento deixou arquivos temporários.")
            report.update(ok=True, tkinter=True, queue=True, worker=True,
                          error_handling=True, saved_bytes=app.saved_bytes,
                          pymupdf=pymupdf.VersionBind)
    except Exception:
        report.update(ok=False, error=traceback.format_exc())
    finally:
        if app is not None:
            app.cancel_event.set()
            if app.worker is not None:
                app.worker.join(timeout=5)
            app.close()
        elif root is not None:
            root.destroy()
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.get("ok") else 1
