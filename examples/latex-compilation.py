#!/usr/bin/env python3
"""
Example: Compiling LaTeX documents through MCP
"""

import requests


def compile_latex(content: str, output_format: str = "pdf"):
    """Compile LaTeX document through MCP server"""

    url = "http://localhost:8000/tools/execute"

    payload = {
        "tool": "compile_latex",
        "arguments": {"content": content, "format": output_format},
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            return result["result"]
        else:
            print(f"Error: {result.get('error')}")
            return None
    else:
        print(f"HTTP Error: {response.status_code}")
        return None


# Example LaTeX documents
if __name__ == "__main__":
    # Example 1: Simple article
    print("Example 1: Simple Article")
    print("-" * 50)

    simple_article = r"""
\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{hyperref}

\title{MCP LaTeX Integration}
\author{MCP Server}
\date{\today}

\begin{document}

\maketitle

\begin{abstract}
This document demonstrates the LaTeX compilation capabilities of the MCP server.
It showcases various LaTeX features including mathematical equations, lists, and
formatting.
\end{abstract}

\section{Introduction}
The MCP server provides seamless LaTeX compilation through a simple API interface.
This allows for dynamic document generation with full LaTeX capabilities.

\section{Mathematical Equations}
Here are some example equations:

\subsection{Inline Math}
The quadratic formula is $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

\subsection{Display Math}
\begin{equation}
    E = mc^2
\end{equation}

\begin{align}
    \nabla \cdot \mathbf{E} &= \frac{\rho}{\epsilon_0} \\
    \nabla \cdot \mathbf{B} &= 0 \\
    \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
    \nabla \times \mathbf{B} &= \mu_0 \mathbf{j} + \mu_0 \epsilon_0
                                  \frac{\partial \mathbf{E}}{\partial t}
\end{align}

\section{Lists and Formatting}
\subsection{Itemized List}
\begin{itemize}
    \item First item
    \item Second item with \textbf{bold} text
    \item Third item with \textit{italic} text
\end{itemize}

\subsection{Enumerated List}
\begin{enumerate}
    \item Step one
    \item Step two
    \item Step three
\end{enumerate}

\section{Conclusion}
The MCP LaTeX integration provides a powerful way to generate professional
documents programmatically.

\end{document}
    """

    result = compile_latex(simple_article)
    if result:
        print(f"✅ PDF created: {result.get('output_path')}")

    print("\n")

    # Example 2: Technical report
    print("Example 2: Technical Report")
    print("-" * 50)

    technical_report = r"""
\documentclass[11pt,a4paper]{report}
\usepackage{amsmath,amssymb}
\usepackage{algorithm2e}
\usepackage{listings}
\usepackage{xcolor}

\lstset{
    basicstyle=\ttfamily\small,
    keywordstyle=\color{blue},
    commentstyle=\color{green!50!black},
    stringstyle=\color{red},
    showstringspaces=false,
    numbers=left,
    numberstyle=\tiny\color{gray}
}

\title{Technical Report: MCP Server Architecture}
\author{Engineering Team}
\date{\today}

\begin{document}

\maketitle
\tableofcontents

\chapter{System Overview}

\section{Introduction}
This report describes the architecture and implementation of the Model Context
Protocol (MCP) server.

\section{Architecture}
The MCP server follows a microservices architecture with the following
components:

\begin{itemize}
    \item \textbf{Core Server}: Handles MCP protocol communication
    \item \textbf{Tool Registry}: Manages available tools and their configurations
    \item \textbf{Execution Engine}: Runs tools in isolated environments
    \item \textbf{API Gateway}: Provides HTTP/REST interface
\end{itemize}

\chapter{Implementation Details}

\section{Core Algorithm}

\begin{algorithm}[H]
\SetAlgoLined
\KwData{Request $r$, Tool Registry $T$}
\KwResult{Response $response$}

 $tool \gets$ ExtractTool($r$)\;
 \If{$tool \in T$}{
    $params \gets$ ExtractParams($r$)\;
    $validated \gets$ ValidateParams($params$, $T[tool]$)\;
    \eIf{$validated$}{
        $result \gets$ ExecuteTool($tool$, $params$)\;
        $response \gets$ FormatSuccess($result$)\;
    }{
        $response \gets$ FormatError("Invalid parameters")\;
    }
 }
 \Else{
    $response \gets$ FormatError("Tool not found")\;
 }
 \Return{$response$}\;
 \caption{MCP Request Processing}
\end{algorithm}

\section{Code Example}

\begin{lstlisting}[language=Python, caption=MCP Tool Implementation]
class MCPTool:
    def __init__(self, name: str, handler: Callable):
        self.name = name
        self.handler = handler

    async def execute(self, params: dict) -> dict:
        try:
            result = await self.handler(**params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
\end{lstlisting}

\chapter{Performance Analysis}

\section{Benchmarks}
Tool execution times (average over 1000 runs):

\begin{center}
\begin{tabular}{|l|r|r|r|}
\hline
\textbf{Tool} & \textbf{Min (ms)} & \textbf{Avg (ms)} & \textbf{Max (ms)} \\
\hline
format\_check & 12 & 15 & 23 \\
lint & 45 & 52 & 89 \\
compile\_latex & 850 & 920 & 1250 \\
\hline
\end{tabular}
\end{center}

\end{document}
    """

    result = compile_latex(technical_report)
    if result:
        print(f"✅ PDF created: {result.get('output_path')}")

    print("\n")

    # Example 3: Presentation slides (beamer)
    print("Example 3: Presentation Slides")
    print("-" * 50)

    presentation = r"""
\documentclass{beamer}
\usetheme{Madrid}
\usecolortheme{seahorse}

\title{MCP Server}
\subtitle{Model Context Protocol Implementation}
\author{Development Team}
\date{\today}

\begin{document}

\frame{\titlepage}

\begin{frame}
\frametitle{Agenda}
\tableofcontents
\end{frame}

\section{Introduction}

\begin{frame}
\frametitle{What is MCP?}
\begin{itemize}
    \item Model Context Protocol
    \item Standardized tool interface
    \item Language-agnostic design
    \item Extensible architecture
\end{itemize}
\end{frame}

\section{Features}

\begin{frame}
\frametitle{Core Features}
\begin{columns}
\column{0.5\textwidth}
\textbf{Development Tools}
\begin{itemize}
    \item Code formatting
    \item Linting
    \item Static analysis
\end{itemize}

\column{0.5\textwidth}
\textbf{Content Creation}
\begin{itemize}
    \item LaTeX compilation
    \item Manim animations
    \item AI assistance
\end{itemize}
\end{columns}
\end{frame}

\section{Architecture}

\begin{frame}
\frametitle{System Architecture}
\begin{center}
\includegraphics[width=0.8\textwidth]{architecture.png}
\end{center}
\end{frame}

\section{Demo}

\begin{frame}[fragile]
\frametitle{API Example}
\begin{verbatim}
POST /tools/execute
{
  "tool": "compile_latex",
  "arguments": {
    "content": "\\documentclass{article}...",
    "format": "pdf"
  }
}
\end{verbatim}
\end{frame}

\section{Conclusion}

\begin{frame}
\frametitle{Summary}
\begin{itemize}
    \item MCP provides unified tool access
    \item Easy integration with existing systems
    \item Extensible for custom tools
    \item Production-ready implementation
\end{itemize}

\vspace{1cm}
\begin{center}
\Large{Questions?}
\end{center}
\end{frame}

\end{document}
    """

    result = compile_latex(presentation)
    if result:
        print(f"✅ PDF created: {result.get('output_path')}")

    print("\n")
    print("📄 All LaTeX documents compiled!")
    print("Note: Output files are saved in the MCP server's output directory")
