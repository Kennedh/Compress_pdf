# 🚀 Compressor de PDF com Ghostscript

## 📖 Visão Geral
Este script em **Python** é uma funcionalidade simples e robusta para a compressão de arquivos **PDF** utilizando a ferramenta de código aberto **Ghostscript (GS)**.  
Ele permite aplicar diferentes níveis de compressão (*presets*) para otimizar o tamanho do arquivo para variados cenários de uso (tela, e-book, impressão, etc.).

---

## 🛠️ Tecnologias
- **Linguagem:** Python 3.x  
- **Módulos Nativos:** `argparse`, `subprocess`, `os`, `sys`  
- **Requisito Principal:** Ghostscript deve estar instalado no sistema e acessível via `PATH`.

---

## 📦 Instalação do Requisito (Ghostscript)
Para que este script funcione, você deve instalar o Ghostscript no seu sistema operacional:

| Sistema Operacional      | Comando ou Ação                                                                 |
|---------------------------|--------------------------------------------------------------------------------|
| **Linux (Debian/Ubuntu)** | `sudo apt-get install ghostscript`                                             |
| **macOS (via Homebrew)**  | `brew install ghostscript`                                                     |
| **Windows**               | Baixe o instalador oficial no site do [Ghostscript](https://ghostscript.com/releases/gsdnld.html) e certifique-se de adicionar o diretório **bin** ao seu `PATH`. |

---

## 🚀 Uso
O script é executado via linha de comando (terminal/cmd/PowerShell).

### Sintaxe

python compress_pdf.py <ARQUIVO_ENTRADA> <ARQUIVO_SAIDA> [-p PRESET]


### Argumentos e Opções

| Argumento/Opção      | Descrição                                         |
|---------------------|--------------------------------------------------|
| `<ARQUIVO_ENTRADA>`  | Caminho completo do PDF a ser comprimido (ex: documento_grande.pdf) |
| `<ARQUIVO_SAIDA>`    | Caminho e nome do arquivo comprimido gerado (ex: documento_pequeno.pdf) |
| `-p` ou `--preset`   | Nível de compressão do Ghostscript (opcional, padrão: ebook) |

## Presets de Compressão (`-p`)

O preset define a resolução e a qualidade da compactação das imagens no PDF:

| Preset    | Descrição                                  | Uso Ideal                                     |
|-----------|--------------------------------------------|-----------------------------------------------|
| screen    | Resolução de 72 dpi. Compressão máxima.    | Visualização rápida, anexos para e-mail.      |
| ebook     | Resolução de 150 dpi. Bom equilíbrio.      | Distribuição geral, sites, armazenamento. (Padrão) |
| printer   | Resolução de 300 dpi. Alta qualidade.      | PDFs para impressoras padrão.                  |
| prepress  | Maior fidelidade, qualidade preservada.    | Impressão gráfica profissional.                |

## Exemplos de Execução

- Compressão padrão (ebook):
  python compress_pdf.py original.pdf saida.pdf
  
- Compressão extrema (screen):
  python compress_pdf.py relatorio.pdf relatorio_imprimir.pdf -p screen

- Compressão para impressão (printer):
  python compress_pdf.py relatorio.pdf relatorio_imprimir.pdf -p printer

- Compressão com a máxima preservação da qualidade original (prepress)
  python compress_pdf.py entrada.pdf saida.pdf -p prepress

