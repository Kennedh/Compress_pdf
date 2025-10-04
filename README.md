# 🚀 Compressor de PDF com Ghostscript

## 📖 Visão Geral
Este script em **Python** uma funcionalidade simples e robusta para a compressão de arquivos **PDF** utilizando a ferramenta de código aberto **Ghostscript (GS)**.  
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
```bash
python compress_pdf.py <ARQUIVO_ENTRADA> <ARQUIVO_SAIDA> [-p PRESET]
