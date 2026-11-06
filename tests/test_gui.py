"""Verificações da fila e da comunicação entre a janela e o worker."""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
    from pdf_gui import PDFCompressorApp
except ImportError:
    tk = None

from test_compress_pdf import make_pdf
from compress_pdf import CompressionCancelled


@unittest.skipIf(tk is None, "Tkinter indisponível")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ambiente gráfico indisponível: {exc}")
        self.root.withdraw()
        self.app = PDFCompressorApp(self.root)
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.cleanup_window)
        self.folder = Path(self.directory.name)

    def cleanup_window(self):
        self.app.cancel_event.set()
        if self.app.worker:
            self.app.worker.join(timeout=5)
        try:
            self.app.close()
        except tk.TclError:
            pass

    def add(self, paths):
        with patch("pdf_gui.filedialog.askopenfilenames", return_value=[str(p) for p in paths]):
            self.app.add_files()

    def wait_done(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.root.update()
            if str(self.app.start_button["state"]) == "normal":
                break
            time.sleep(0.01)
        else:
            self.fail("A interface não concluiu o processamento em 15 segundos.")
        self.assertEqual(self.callback_errors, [])

    def test_batch_avoids_collisions_continues_after_error_and_remains_responsive(self):
        if self.app.engine_version is None:
            self.skipTest("PyMuPDF indisponível")
        folder_a = self.folder / "a"
        folder_b = self.folder / "b"
        folder_a.mkdir()
        folder_b.mkdir()
        source_a = folder_a / "relatorio.pdf"
        source_b = folder_b / "relatorio.pdf"
        corrupt = self.folder / "corrompido.pdf"
        source_a.write_bytes(make_pdf(image=True))
        source_b.write_bytes(make_pdf())
        corrupt.write_bytes(b"%PDF-1.4\ninvalid")
        existing = self.folder / "relatorio_comprimido.pdf"
        existing.write_bytes(b"existing")
        self.add([source_a, corrupt, source_b, source_a])
        self.assertEqual(len(self.app.files), 3)
        self.app.destination.set(str(self.folder))
        heartbeat = []
        self.root.after(20, lambda: heartbeat.append(True))
        self.app.start()
        self.wait_done()
        self.assertTrue(heartbeat)
        statuses = [self.app.tree.set(item, "status") for item in self.app.files]
        self.assertEqual(statuses, ["Concluído", "Erro · veja detalhes", "Sem redução"])
        self.assertEqual(existing.read_bytes(), b"existing")
        self.assertTrue((self.folder / "relatorio_comprimido_2.pdf").is_file())
        self.assertTrue((self.folder / "relatorio_comprimido_3.pdf").is_file())
        self.assertFalse((self.folder / "corrompido_comprimido.pdf").exists())
        self.assertGreater(self.app.saved_bytes, 0)
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_cancel_marks_remaining_files_and_restores_controls(self):
        source = self.folder / "original.pdf"
        source.write_bytes(make_pdf())
        self.add([source])
        def wait_for_cancel(*_args, **kwargs):
            kwargs["cancel_event"].wait(3)
            raise CompressionCancelled("cancelado")
        with patch("pdf_gui.check_pymupdf", return_value="2.1"), patch(
            "pdf_gui.compress_pdf", side_effect=wait_for_cancel
        ):
            self.app.start()
            self.root.after(30, self.app.cancel)
            self.wait_done()
        item = next(iter(self.app.files))
        self.assertEqual(self.app.tree.set(item, "status"), "Cancelado")
        self.assertEqual(str(self.app.add_button["state"]), "normal")
        self.assertFalse((self.folder / "original_comprimido.pdf").exists())
