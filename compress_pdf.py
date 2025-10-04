
import argparse
import subprocess
import os
import sys


def compress_pdf(input_path, output_path, preset):
    """
    Presets de compressão do Ghostscript:
     - screen: resolução de 72 dpi (ideal para visualização na tela)
     - ebook: resolução de 150 dpi (bom equilíbrio para PDFs pequenos)
     - printer: resolução de 300 dpi (alta qualidade para impressão)
     - prepress: maior fidelidade, preservando a qualidade máxima
    """
    # Verifica se o arquivo de entrada existe
    if not os.path.isfile(input_path):
        print(f"Erro: arquivo de entrada '{input_path}' não encontrado.")
        sys.exit(1)

    # O comando principal irá falhar se o Ghostscript não estiver instalado,

    # Monta o comando do Ghostscript
    gs_cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{preset}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-sOutputFile=" + output_path,
        input_path
    ]

    print(f"Comprimindo '{input_path}' com o preset '{preset}'...")

    # Executa o comando
    try:
        subprocess.run(gs_cmd, check=True)
        print(f"Compressão concluída! Arquivo salvo como '{output_path}'.")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar o Ghostscript: {e}")
        print("Verifique se o Ghostscript está instalado e no PATH do sistema.")
        sys.exit(1)
    except FileNotFoundError:
        print("Erro: 'gs' não foi encontrado.")
        print("Verifique se o Ghostscript está instalado e se o diretório 'bin' está no PATH do sistema.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compacta PDF com Ghostscript"
    )
    parser.add_argument("input_file", help="Caminho do PDF de entrada.")
    parser.add_argument("output_file", help="Caminho onde o PDF comprimido será salvo.")
    parser.add_argument(
        "-p",
        "--preset",
        choices=["screen", "ebook", "printer", "prepress"],
        default="ebook",
        help="Define o nível de compressão (padrão: 'ebook')."
    )
    args = parser.parse_args()
    compress_pdf(args.input_file, args.output_file, args.preset)

# Uso via cmd/Power Shell: python compressor_pdf.py entrada.pdf saida.pdf -p printer