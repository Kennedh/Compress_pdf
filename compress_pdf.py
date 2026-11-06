"""Compressão de PDFs com interface desktop e linha de comando."""

import argparse
from dataclasses import dataclass
from importlib import metadata, util
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from app_version import VERSION


PRESETS = {
    "screen": ("Máxima compressão", "72 dpi · arquivos menores para visualização em tela"),
    "ebook": ("Equilibrado", "150 dpi · equilíbrio entre tamanho e qualidade"),
    "printer": ("Alta qualidade", "300 dpi · indicado para impressão"),
    "prepress": ("Preservar qualidade", "Otimização sem reduzir a qualidade das imagens"),
}


class CompressionError(Exception):
    """Erro que pode ser apresentado diretamente ao usuário."""


class CompressionCancelled(CompressionError):
    """Processamento interrompido pelo usuário."""


@dataclass(frozen=True)
class CompressionResult:
    input_path: Path
    output_path: Path
    original_size: int
    compressed_size: int
    elapsed_seconds: float

    @property
    def saved_bytes(self):
        return self.original_size - self.compressed_size

    @property
    def reduction_percent(self):
        return 100 * self.saved_bytes / self.original_size if self.original_size else 0


def format_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024


def check_pymupdf():
    """Confere a dependência sem carregar a biblioteca nativa na thread da interface."""
    try:
        version = metadata.version("PyMuPDF")
        available = util.find_spec("pymupdf") is not None
    except (metadata.PackageNotFoundError, ImportError, ValueError):
        available = False
    if not available:
        raise CompressionError(
            "PyMuPDF não encontrado neste Python. Execute: "
            "python -m pip install -r requirements.txt"
        )
    return version


def validate_pdf(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise CompressionError(f"Arquivo não encontrado: {source}")
    if source.suffix.lower() != ".pdf":
        raise CompressionError(f"Selecione um arquivo com extensão .pdf: {source.name}")
    try:
        with source.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise CompressionError(f"O arquivo não contém um cabeçalho PDF: {source.name}")
    except OSError as exc:
        raise CompressionError(f"Não foi possível ler {source.name}: {exc}") from exc
    return source


def _run_process(command, cancel_event, timeout):
    # O log em disco evita acumular a saída na memória ou bloquear pipes.
    with tempfile.TemporaryFile() as log:
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **options) as process:
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise CompressionCancelled("Compressão cancelada.")
                    if time.monotonic() >= deadline:
                        raise CompressionError(f"Tempo limite de {timeout:g} segundos excedido.")
                    try:
                        process.wait(timeout=0.1)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            if process.returncode:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 4000))
                detail = log.read().decode("utf-8", errors="replace").strip()
                raise CompressionError(
                    "O PyMuPDF não conseguiu processar o PDF. "
                    "Verifique se está íntegro e se não exige senha.\n" + detail
                )


def _run_pymupdf(source, target, preset, cancel_event, timeout):
    # Um processo permite interromper chamadas nativas e mantém o Tkinter responsivo.
    if getattr(sys, "frozen", False):
        error_log = Path(target).with_suffix(".error.log")
        command = [sys.executable, "--pdf-worker", str(source), str(target), preset, str(error_log)]
        try:
            _run_process(command, cancel_event, timeout)
        except CompressionCancelled:
            raise
        except CompressionError as exc:
            if error_log.is_file():
                raise CompressionError(error_log.read_text(encoding="utf-8")[-4000:]) from exc
            raise
        finally:
            error_log.unlink(missing_ok=True)
        return
    command = [
        sys.executable, "-X", "utf8",
        str(Path(__file__).with_name("pdf_engine.py")),
        str(source), str(target), preset,
    ]
    _run_process(command, cancel_event, timeout)


def compress_pdf(input_path, output_path, preset="ebook", *, overwrite=False,
                 cancel_event=None, timeout=300):
    """Gera uma saída segura sem alterar o original ou publicar um PDF parcial.

    Se o PyMuPDF gerar um arquivo maior, a saída será uma cópia do original.
    O arquivo temporário fica no destino para permitir publicação atômica.
    """
    started = time.monotonic()
    if preset not in PRESETS:
        raise CompressionError(f"Preset inválido: {preset}")
    if not math.isfinite(timeout) or timeout <= 0:
        raise CompressionError("O tempo limite deve ser um número positivo e finito.")
    source = validate_pdf(input_path)
    target = Path(output_path).expanduser().resolve()
    if source == target or (target.exists() and os.path.samefile(source, target)):
        raise CompressionError("A saída deve ser diferente do PDF original.")
    if target.suffix.lower() != ".pdf":
        raise CompressionError("O arquivo de saída deve ter extensão .pdf.")
    if not target.parent.is_dir():
        raise CompressionError(f"A pasta de destino não existe: {target.parent}")
    if target.exists() and not overwrite:
        raise CompressionError(f"A saída já existe: {target.name}. Escolha outro nome ou use --force.")
    if cancel_event is not None and cancel_event.is_set():
        raise CompressionCancelled("Compressão cancelada.")
    check_pymupdf()
    temporary = None
    try:
        original_size = source.stat().st_size
        descriptor, name = tempfile.mkstemp(prefix=".compress-", suffix=".pdf", dir=target.parent)
        os.close(descriptor)
        temporary = Path(name)
        _run_pymupdf(source, temporary, preset, cancel_event, timeout)
        validate_pdf(temporary)
        if temporary.stat().st_size >= original_size:
            shutil.copyfile(source, temporary)
        if cancel_event is not None and cancel_event.is_set():
            raise CompressionCancelled("Compressão cancelada.")
        compressed_size = temporary.stat().st_size
        if overwrite:
            os.replace(temporary, target)
        elif os.name == "nt":
            # No Windows, rename falha se o destino existir.
            os.rename(temporary, target)
        else:
            # Publicação atômica sem substituir um destino criado durante o trabalho.
            os.link(temporary, target)
        return CompressionResult(source, target, original_size, compressed_size,
                                 time.monotonic() - started)
    except OSError as exc:
        raise CompressionError(f"Não foi possível concluir a compressão: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--pdf-worker":
        from pdf_engine import main as worker_main
        return worker_main(argv[1:])
    if argv and argv[0] == "--smoke-test":
        from release_smoke import run
        if len(argv) != 2:
            return 2
        return run(argv[1])
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Compacta PDFs com PyMuPDF. Sem argumentos, abre a interface.")
    parser.add_argument("--version", action="version", version=f"Compress PDF {VERSION}")
    parser.add_argument("input_file", nargs="?", help="PDF de entrada.")
    parser.add_argument("output_file", nargs="?", help="PDF de saída.")
    parser.add_argument("-p", "--preset", choices=PRESETS, default="ebook", help="Qualidade (padrão: ebook).")
    parser.add_argument("--gui", action="store_true", help="Abre a interface gráfica.")
    parser.add_argument("--force", action="store_true", help="Permite substituir uma saída existente.")
    parser.add_argument("--timeout", type=float, default=300, help="Tempo limite por PDF, em segundos (padrão: 300).")
    args = parser.parse_args(argv)
    if args.gui or (args.input_file is None and args.output_file is None):
        if args.input_file is not None or args.output_file is not None:
            parser.error("Use --gui sem os caminhos de entrada e saída.")
        try:
            from pdf_gui import launch
            launch()
        except ImportError as exc:
            print(f"Não foi possível abrir a interface. Verifique a instalação do Tkinter: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.input_file is None or args.output_file is None:
        parser.error("Informe os dois caminhos: entrada.pdf saida.pdf.")
    try:
        print(f"Comprimindo com o preset '{args.preset}'...", flush=True)
        result = compress_pdf(args.input_file, args.output_file, args.preset,
                              overwrite=args.force, timeout=args.timeout)
    except (CompressionError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCompressão interrompida.", file=sys.stderr)
        return 130
    print(f"Salvo em: {result.output_path}")
    print(f"{format_size(result.original_size)} -> {format_size(result.compressed_size)} "
          f"| redução de {result.reduction_percent:.1f}% | {result.elapsed_seconds:.1f}s")
    if not result.saved_bytes:
        print("O processamento não reduziu o tamanho; a saída mantém o conteúdo original.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
