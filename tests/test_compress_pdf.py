"""Testes de segurança e integração. Execute: python -m unittest discover -s tests -v."""

from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

try:
    import pymupdf
except ImportError:
    pymupdf = None

from compress_pdf import (
    PRESETS, CompressionCancelled, CompressionError, _run_process,
    compress_pdf, check_pymupdf,
)


def make_pdf(image=False):
    """PDF válido de uma página; imagem RGB sem compressão para testar redução."""
    content = b"q 200 0 0 200 20 20 cm /Im0 Do Q" if image else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 240 240] "
        + (b"/Resources << /XObject << /Im0 5 0 R >> >> " if image else b"")
        + b"/Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    if image:
        pixels = bytes(channel for y in range(512) for x in range(512)
                       for channel in (x % 256, y % 256, (x + y) % 256))
        objects.append(
            b"<< /Type /XObject /Subtype /Image /Width 512 /Height 512 "
            b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length "
            + str(len(pixels)).encode() + b" >>\nstream\n" + pixels + b"\nendstream"
        )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


class FileFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.source = self.folder / "original.pdf"
        self.source.write_bytes(make_pdf())
        self.target = self.folder / "saida.pdf"


class SafetyTests(FileFixture):
    def test_frozen_worker_reports_error_and_removes_temporary_files(self):
        def fail(command, *_args):
            self.assertEqual(command[1], "--pdf-worker")
            Path(command[3]).write_bytes(b"partial")
            Path(command[5]).write_text("Erro no worker empacotado", encoding="utf-8")
            raise CompressionError("processo falhou")
        with patch.object(sys, "frozen", True, create=True), patch(
            "compress_pdf._run_process", side_effect=fail
        ):
            with self.assertRaisesRegex(CompressionError, "Erro no worker empacotado"):
                compress_pdf(self.source, self.target)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_frozen_worker_keeps_cancellation_and_removes_error_report(self):
        def cancel(command, *_args):
            Path(command[5]).write_text("erro anterior", encoding="utf-8")
            raise CompressionCancelled("cancelado")
        with patch.object(sys, "frozen", True, create=True), patch(
            "compress_pdf._run_process", side_effect=cancel
        ):
            with self.assertRaises(CompressionCancelled):
                compress_pdf(self.source, self.target)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_original_cannot_be_overwritten_even_with_force(self):
        original = self.source.read_bytes()
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.source, overwrite=True)
        self.assertEqual(self.source.read_bytes(), original)

    def test_existing_output_requires_force(self):
        self.target.write_bytes(b"existing")
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), b"existing")

    def test_invalid_input_and_preset(self):
        self.source.write_bytes(b"not a PDF")
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.target)
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.target, "invalid")
        self.assertFalse(self.target.exists())

    def test_invalid_timeout(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(CompressionError):
                compress_pdf(self.source, self.target, timeout=timeout)

    def test_missing_source_and_destination(self):
        with self.assertRaises(CompressionError):
            compress_pdf(self.folder / "missing.pdf", self.target)
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.folder / "missing" / "out.pdf")

    def test_cancel_before_start_creates_no_output(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(CompressionCancelled):
            compress_pdf(self.source, self.target, cancel_event=event)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_failed_process_preserves_existing_output_and_cleans_temporary(self):
        self.target.write_bytes(b"existing")
        def fail(_source, output, *_args):
            Path(output).write_bytes(b"partial")
            raise CompressionError("falha simulada")
        with patch("compress_pdf._run_pymupdf", side_effect=fail):
            with self.assertRaises(CompressionError):
                compress_pdf(self.source, self.target, overwrite=True)
        self.assertEqual(self.target.read_bytes(), b"existing")
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_destination_created_during_processing_is_preserved(self):
        def race(_source, output, *_args):
            Path(output).write_bytes(make_pdf())
            self.target.write_bytes(b"another application")
        with patch("compress_pdf._run_pymupdf", side_effect=race):
            with self.assertRaises(CompressionError):
                compress_pdf(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), b"another application")
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_timeout_kills_active_process(self):
        with self.assertRaisesRegex(CompressionError, "Tempo limite"):
            _run_process([sys.executable, "-c", "import time; time.sleep(10)"], None, 0.2)

    def test_cancel_kills_active_process(self):
        event = threading.Event()
        timer = threading.Timer(0.2, event.set)
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaises(CompressionCancelled):
            _run_process([sys.executable, "-c", "import time; time.sleep(10)"], event, 5)

    def test_cli_validation(self):
        result = subprocess.run(
            [sys.executable, "compress_pdf.py", str(self.source)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(result.returncode, 2)


    def test_missing_dependency_has_installation_instructions(self):
        from importlib import metadata
        with patch("compress_pdf.metadata.version", side_effect=metadata.PackageNotFoundError):
            with self.assertRaisesRegex(CompressionError, "pip install"):
                check_pymupdf()

    def test_cancel_during_processing_removes_temporary_output(self):
        event = threading.Event()
        def cancel(_source, output, _preset, *_args):
            Path(output).write_bytes(b"partial")
            event.set()
            raise CompressionCancelled("cancelado")
        with patch("compress_pdf._run_pymupdf", side_effect=cancel):
            with self.assertRaises(CompressionCancelled):
                compress_pdf(self.source, self.target, cancel_event=event)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob(".compress-*")), [])


@unittest.skipIf(pymupdf is None, "PyMuPDF indisponível")
class PyMuPDFIntegrationTests(FileFixture):
    def test_worker_error_is_reported_without_a_console(self):
        from pdf_engine import main as worker_main
        self.source.write_bytes(b"%PDF-1.4\ninvalid document")
        report = self.folder / "error.log"
        with patch.object(sys, "stderr", None):
            code = worker_main([str(self.source), str(self.target), "ebook", str(report)])
        self.assertEqual(code, 1)
        self.assertIn("processar o PDF", report.read_text(encoding="utf-8"))
        self.assertFalse(self.target.exists())

    def test_real_compression_all_presets_and_output_readability(self):
        self.source.write_bytes(make_pdf(image=True))
        original = self.source.read_bytes()
        for preset in PRESETS:
            with self.subTest(preset=preset):
                output = self.folder / f"{preset}.pdf"
                result = compress_pdf(self.source, output, preset)
                self.assertGreater(result.saved_bytes, 0)
                self.assertEqual(output.stat().st_size, result.compressed_size)
                self.assertEqual(self.source.read_bytes(), original)
                with pymupdf.open(output) as document:
                    self.assertEqual(document.page_count, 1)
                    self.assertGreater(len(document[0].get_pixmap().samples), 0)
                    if preset == "screen":
                        self.assertLess(document[0].get_images()[0][2], 512)
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_larger_result_keeps_original_bytes(self):
        result = compress_pdf(self.source, self.target)
        self.assertEqual(result.saved_bytes, 0)
        self.assertEqual(self.source.read_bytes(), self.target.read_bytes())

    def test_real_error_preserves_existing_destination(self):
        self.source.write_bytes(b"%PDF-1.4\ninvalid document")
        self.target.write_bytes(b"existing")
        with self.assertRaises(CompressionError):
            compress_pdf(self.source, self.target, overwrite=True)
        self.assertEqual(self.target.read_bytes(), b"existing")
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_cli_compression_with_unicode_and_spaces(self):
        destination = self.folder / "100% completo"
        destination.mkdir()
        self.target = destination / "saida.pdf"
        source = self.folder / "relatório de teste.pdf"
        source.write_bytes(make_pdf(image=True))
        result = subprocess.run(
            [sys.executable, "compress_pdf.py", str(source), str(self.target), "-p", "screen"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.is_file())


    def test_preserve_quality_keeps_pixels_text_and_document_features(self):
        self.source.write_bytes(make_pdf(image=True))
        with pymupdf.open(self.source) as document:
            page = document[0]
            page.insert_text((20, 230), "Resumo do documento")
            page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(10, 10, 80, 20),
                              "uri": "https://example.com"})
            page.add_text_annot((220, 220), "Comentario de teste")
            widget = pymupdf.Widget()
            widget.field_name = "nome"
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            widget.field_value = "Teste"
            widget.rect = pymupdf.Rect(10, 2, 80, 12)
            page.add_widget(widget)
            document.set_metadata({"title": "Documento de teste"})
            document.set_toc([[1, "Resumo", 1]])
            document.save(self.folder / "com_recursos.pdf")
        source = self.folder / "com_recursos.pdf"
        result = compress_pdf(source, self.target, "prepress")
        self.assertGreater(result.saved_bytes, 0)
        with pymupdf.open(source) as before, pymupdf.open(self.target) as after:
            self.assertEqual(before[0].get_pixmap().samples, after[0].get_pixmap().samples)
            self.assertEqual(before[0].get_text(), after[0].get_text())
            self.assertEqual(after.metadata["title"], "Documento de teste")
            self.assertEqual(before.get_toc(), after.get_toc())
            self.assertEqual(after[0].get_links()[0]["uri"], "https://example.com")
            self.assertEqual(next(after[0].widgets()).field_value, "Teste")
            page = after[0]
            self.assertEqual(next(page.annots()).info["content"], "Comentario de teste")

    def test_password_protected_pdf_is_rejected_without_touching_output(self):
        with pymupdf.open(self.source) as document:
            document.save(self.folder / "protegido.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256,
                          owner_pw="dono", user_pw="senha")
        self.target.write_bytes(b"existing")
        with self.assertRaisesRegex(CompressionError, "senha"):
            compress_pdf(self.folder / "protegido.pdf", self.target, overwrite=True)
        self.assertEqual(self.target.read_bytes(), b"existing")
        self.assertEqual(list(self.folder.glob(".compress-*")), [])

    def test_compression_does_not_need_programs_on_path(self):
        self.source.write_bytes(make_pdf(image=True))
        import os
        with patch.dict(os.environ, {"PATH": ""}):
            result = compress_pdf(self.source, self.target)
        self.assertGreater(result.saved_bytes, 0)


if __name__ == "__main__":
    unittest.main()
