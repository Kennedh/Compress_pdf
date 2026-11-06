"""Worker de compressão com PyMuPDF, executado em um processo Python separado."""

import sys
from pathlib import Path


# DPI alvo e qualidade JPEG. Imagens monocromáticas ficam preservadas.
IMAGE_PROFILES = {
    "screen": (72, 50),
    "ebook": (150, 75),
    "printer": (300, 90),
}


def optimize_pdf(source, target, preset):
    import pymupdf

    if preset not in (*IMAGE_PROFILES, "prepress"):
        raise ValueError(f"Perfil inválido: {preset}")
    if not hasattr(pymupdf.Document, "rewrite_images"):
        raise ValueError("Atualize o PyMuPDF: python -m pip install -r requirements.txt")

    with pymupdf.open(source) as document:
        if not document.is_pdf:
            raise ValueError("O arquivo não é um PDF válido.")
        if document.needs_pass:
            raise ValueError("O PDF exige senha. Abra uma cópia sem senha antes de comprimir.")
        page_count = document.page_count
        if page_count == 0:
            raise ValueError("O PDF não contém páginas.")

        if preset in IMAGE_PROFILES:
            dpi, quality = IMAGE_PROFILES[preset]
            document.rewrite_images(
                dpi_threshold=dpi * 3 // 2,
                dpi_target=dpi,
                quality=quality,
                bitonal=False,
            )
        # Otimização estrutural em todos os perfis, sem rasterizar as páginas.
        document.save(
            target,
            garbage=3,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            use_objstms=1,
            encryption=pymupdf.PDF_ENCRYPT_KEEP,
        )

    with pymupdf.open(target) as result:
        if not result.is_pdf or result.page_count != page_count:
            raise ValueError("O resultado não preservou a quantidade de páginas do original.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    error_log = Path(args[3]) if len(args) == 4 else None
    try:
        if len(args) not in (3, 4):
            raise ValueError("Informe entrada, saída e perfil.")
        optimize_pdf(*args[:3])
    except Exception as exc:
        message = f"Não foi possível processar o PDF: {exc}"
        if error_log is not None:
            error_log.write_text(message, encoding="utf-8")
        elif sys.stderr is not None:
            print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
