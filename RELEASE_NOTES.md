Compressão de PDFs com interface desktop em português, processamento em lote e PyMuPDF.

- Seleção de vários PDFs, quatro perfis e comparação de tamanho antes e depois.
- Modo **Preservar qualidade**, sem reduzir a qualidade das imagens.
- Cancelamento, tempo limite e proteção dos arquivos originais.
- Python, Tkinter e PyMuPDF incluídos nos pacotes: não é preciso instalar Python ou Ghostscript.

| Sistema | Arquivo |
|---|---|
| Windows 64 bits | `CompressPDF-v1.0.0-windows-x64.zip` |
| Linux 64 bits | `CompressPDF-v1.0.0-linux-x64.tar.gz` |
| macOS Intel | `CompressPDF-v1.0.0-macos-x64.zip` |
| macOS Apple Silicon | `CompressPDF-v1.0.0-macos-arm64.zip` |

**Windows:** extraia o ZIP inteiro e abra `CompressPDF/CompressPDF.exe`. Mantenha a pasta `_internal` junto do executável.

**macOS:** extraia o ZIP e abra `CompressPDF.app`. O pacote usa assinatura local, sem notarização da Apple; o sistema pode pedir autorização em Privacidade e Segurança na primeira abertura.

**Linux:** extraia o arquivo e execute `./CompressPDF/CompressPDF`. O pacote é construído no Ubuntu 22.04 e requer uma sessão gráfica e bibliotecas de sistema compatíveis.

Os arquivos `*.build.json` registram o teste de cada pacote: abertura do Tkinter, compressão em segundo plano, preservação de páginas e texto e tratamento de PDF inválido. As somas SHA-256 estão em `SHA256SUMS.txt`.
